STAY_DATES = {"check_in": "2026-12-04", "check_out": "2026-12-07"}

KYOTO_SEARCH_BODY = {
    "destination": "Kyoto",
    **STAY_DATES,
    "guests": 2,
    "rooms": 1,
    "max_nightly_budget": 250.0,
    "min_rating": 8.0,
    "amenities": ["WIFI", "BREAKFAST"],
    "preferences": ["quiet room"],
}

LISBON_SEARCH_BODY = {
    "destination": "Lisbon",
    **STAY_DATES,
    "max_nightly_budget": 160.0,
    "min_rating": 7.0,
    "amenities": ["WIFI"],
}

COMPARE_BODY = {
    "hotel_ids": ["hotel-lis-01", "hotel-lis-02", "hotel-xxx-99"],
    **STAY_DATES,
    "rooms": 1,
    "guests": 2,
    "preferences": ["river view"],
}
