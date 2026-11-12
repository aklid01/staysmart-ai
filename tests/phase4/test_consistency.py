import re

from staysmart.providers.mock.dataset import load_dataset
from staysmart.rag.corpus import load_corpus

AMENITY_PHRASES = {
    "WIFI": "wi-fi",
    "BREAKFAST": "breakfast",
    "AIR_CONDITIONING": "air conditioning",
    "POOL": "pool",
    "GYM": "gym",
    "PARKING": "parking",
    "SPA": "spa",
    "PET_FRIENDLY": "pet-friendly",
    "RESTAURANT": "restaurant",
    "SHUTTLE": "shuttle",
}

BED_PHRASES = {
    "queen": "queen",
    "king": "king",
    "twin": "twin",
    "double": "double",
    "futon": "futon",
    "two queens": "two queen",
}

CHECK_IN_TIMES = {"lisbon-pt": ("15:00", "11:00"), "kyoto-jp": ("15:00", "10:00"), "vancouver-ca": ("16:00", "11:00")}

UNTIL_PATTERN = re.compile(r"until (\d+) days? before check-in")
PENALTY_PATTERN = re.compile(r"(\d+)-night penalty")
DENYLIST_PATTERNS = [re.compile(r"\$\s*\d"), re.compile(r"\bper night\b"), re.compile(r"\btotal price\b"), re.compile(r"\bnightly rate\b"), re.compile(r"\bsold out\b"), re.compile(r"\brooms left\b")]


def corpus_maps(corpus_path, settings):
    docs = load_corpus(corpus_path)
    dataset = load_dataset(settings.dataset_path)
    by_hotel = {}
    by_doc_id = {}
    for doc in docs:
        by_doc_id[doc.doc_id] = doc
        if doc.hotel_id:
            by_hotel.setdefault(doc.hotel_id, {})[doc.category] = doc
    return dataset, by_hotel, by_doc_id


def test_cancellation_docs_match_dataset_numbers(corpus_path, settings):
    dataset, by_hotel, _ = corpus_maps(corpus_path, settings)
    for hotel in dataset.hotels:
        text = by_hotel[hotel.hotel_id]["cancellation"].body.lower()
        policy = hotel.cancellation_policy
        if policy.refundable:
            match = UNTIL_PATTERN.search(text)
            assert match, hotel.hotel_id
            assert int(match.group(1)) == policy.free_cancellation_days
            assert "non-refundable" not in text
            if policy.policy_type == "partial":
                penalty = PENALTY_PATTERN.search(text)
                assert penalty, hotel.hotel_id
                assert int(penalty.group(1)) == policy.penalty_nights
            else:
                assert policy.penalty_nights == 0
        else:
            assert "non-refundable" in text
            assert not UNTIL_PATTERN.search(text)


def test_pet_policy_matches_dataset_amenity(corpus_path, settings):
    dataset, by_hotel, _ = corpus_maps(corpus_path, settings)
    for hotel in dataset.hotels:
        text = by_hotel[hotel.hotel_id]["pet_policy"].body
        pet_friendly = "PET_FRIENDLY" in hotel.amenities
        if pet_friendly:
            assert "Pets are allowed" in text
            assert "Pets are not allowed" not in text
        else:
            assert "Pets are not allowed" in text
            assert "Pets are allowed" not in text


def test_amenities_docs_match_dataset_amenities(corpus_path, settings):
    dataset, by_hotel, _ = corpus_maps(corpus_path, settings)
    for hotel in dataset.hotels:
        text = by_hotel[hotel.hotel_id]["amenities"].body.lower()
        owned = set(hotel.amenities)
        for amenity, phrase in AMENITY_PHRASES.items():
            if amenity in owned:
                assert phrase in text, f"{hotel.hotel_id} missing {phrase}"
            elif amenity != "WIFI":
                assert not re.search(rf"\b{re.escape(phrase)}\b", text), f"{hotel.hotel_id} claims {phrase}"


def test_rooms_docs_match_room_types(corpus_path, settings):
    dataset, by_hotel, _ = corpus_maps(corpus_path, settings)
    for hotel in dataset.hotels:
        text = by_hotel[hotel.hotel_id]["rooms"].body
        for room in hotel.room_types:
            assert room.name in text, hotel.hotel_id
            assert f"sleeps up to {room.max_occupancy} guests" in text
            assert BED_PHRASES[room.bed_type] in text.lower()


def test_general_docs_mention_star_rating(corpus_path, settings):
    dataset, by_hotel, _ = corpus_maps(corpus_path, settings)
    for hotel in dataset.hotels:
        text = by_hotel[hotel.hotel_id]["general"].body
        assert f"{hotel.star_rating}-star" in text


def test_checkin_docs_pin_destination_times(corpus_path, settings):
    docs = load_corpus(corpus_path)
    destination_docs = {doc.destination_id: doc for doc in docs if doc.destination_id}
    for destination_id, (check_in, check_out) in CHECK_IN_TIMES.items():
        text = destination_docs[destination_id].body
        assert f"Check-in starts at {check_in}" in text
        assert f"Check-out is by {check_out}" in text


def test_no_document_contains_pricing_or_availability_phrases(corpus_path):
    for doc in load_corpus(corpus_path):
        for pattern in DENYLIST_PATTERNS:
            assert not pattern.search(doc.body), f"{doc.doc_id} matched {pattern.pattern}"
