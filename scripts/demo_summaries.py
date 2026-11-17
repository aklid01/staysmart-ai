import json
import os
from pathlib import Path
from typing import Any


def quote_summary(quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "room_type_id": quote["room_type_id"],
        "nights": quote["nights"],
        "nights_available": quote["nights_available"],
        "nightly_rates": quote["nightly_rates"],
        "avg_nightly_rate": quote["avg_nightly_rate"],
        "total_price": quote["total_price"],
        "available": quote["available"],
        "partially_available": quote["partially_available"],
        "sold_out_dates": quote["sold_out_dates"],
    }


def hit_summary(hit: dict[str, Any]) -> dict[str, Any]:
    hotel = hit["hotel"]
    quote = hit["quote"]
    return {
        "hotel_id": hotel["hotel_id"],
        "hotel_name": hotel["name"],
        "location": hotel["location"],
        "guest_rating": hotel["guest_rating"],
        "star_rating": hotel["star_rating"],
        "amenities": hotel["amenities"],
        "matched_amenities": hit["matched_amenities"],
        "cancellation_policy": hotel["cancellation_policy"]["policy_type"],
        "refundable": hotel["cancellation_policy"]["refundable"],
        "room_type_id": quote["room_type_id"],
        "nights": quote["nights"],
        "nights_available": quote["nights_available"],
        "nightly_rates": quote["nightly_rates"],
        "avg_nightly_rate": quote["avg_nightly_rate"],
        "total_price": quote["total_price"],
        "available": quote["available"],
        "partially_available": quote["partially_available"],
        "sold_out_dates": quote["sold_out_dates"],
        "currency": quote["currency"],
        "data_source": quote["data_source"],
        "is_live": quote["is_live"],
    }


def search_summary(structured: dict[str, Any]) -> dict[str, Any]:
    return {
        "destination": structured["query"]["destination"],
        "check_in": structured["query"]["check_in"],
        "check_out": structured["query"]["check_out"],
        "guests": structured["query"]["guests"],
        "rooms": structured["query"]["rooms"],
        "max_nightly_budget": structured["query"]["max_nightly_budget"],
        "min_rating": structured["query"]["min_rating"],
        "required_amenities": structured["query"]["amenities"],
        "preferences": structured["query"]["preferences"],
        "total_found": structured["total_found"],
        "hotel_ids": [hit["hotel"]["hotel_id"] for hit in structured["results"]],
        "unmet_preferences": structured["unmet_preferences"],
        "hits": [hit_summary(hit) for hit in structured["results"]],
    }


def details_summary(structured: dict[str, Any]) -> dict[str, Any]:
    policy = structured["cancellation_policy"]
    return {
        "hotel_id": structured["hotel"]["hotel_id"],
        "hotel_name": structured["hotel"]["name"],
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": structured["rooms"],
        "guests": structured["guests"],
        "currency": structured["currency"],
        "cancellation_policy": policy["policy_type"],
        "refundable": policy["refundable"],
        "free_cancellation_days": policy["free_cancellation_days"],
        "penalty_nights": policy["penalty_nights"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
        "room_quotes": [quote_summary(quote) for quote in structured["room_quotes"]],
    }


def availability_summary(structured: dict[str, Any], rooms: int) -> dict[str, Any]:
    return {
        "hotel_id": structured["hotel_id"],
        "room_type_id": structured["room_type_id"],
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": rooms,
        "currency": structured["currency"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
        "nights_requested": structured["nights_requested"],
        "nights_available": structured["nights_available"],
        "available": structured["available"],
        "sold_out_dates": structured["sold_out_dates"],
        "nightly_rates": structured["nightly_rates"],
        "total_price": structured["total_price"],
    }


def row_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "hotel_id": row["hotel_id"],
        "name": row["name"],
        "location": row["location"],
        "guest_rating": row["guest_rating"],
        "amenities": row["amenities"],
        "cancellation_policy": row["cancellation_policy"],
        "refundable": row["refundable"],
        "nightly_price": row["nightly_price"],
        "total_stay_price": row["total_stay_price"],
        "availability": row["availability"],
    }


def comparison_summary(structured: dict[str, Any], requested_ids: list[str]) -> dict[str, Any]:
    return {
        "hotel_ids_requested": requested_ids,
        "check_in": structured["check_in"],
        "check_out": structured["check_out"],
        "rooms": structured["rooms"],
        "guests": structured["guests"],
        "currency": structured["currency"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
        "rows": [row_summary(row) for row in structured["rows"]],
        "unresolved_hotel_ids": structured["unresolved_hotel_ids"],
        "unmet_preferences": structured["unmet_preferences"],
    }


def policies_summary(structured: dict[str, Any]) -> dict[str, Any]:
    policy = structured["cancellation_policy"]
    return {
        "hotel_id": structured["hotel_id"],
        "hotel_name": structured["hotel_name"],
        "general_info": structured["general_info"],
        "cancellation_policy": policy["policy_type"],
        "refundable": policy["refundable"],
        "free_cancellation_days": policy["free_cancellation_days"],
        "penalty_nights": policy["penalty_nights"],
        "policy_description": policy["description"],
        "pet_policy": structured["pet_policy"],
        "pet_policy_source": structured["pet_policy_source"],
        "check_in_time": structured["check_in_time"],
        "check_out_time": structured["check_out_time"],
        "information_gaps": structured["information_gaps"],
        "data_source": structured["data_source"],
        "is_live": structured["is_live"],
    }


def write_artifact(path: Path, payload: dict[str, Any]) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp_path, path)
    print(f"wrote {path}")
