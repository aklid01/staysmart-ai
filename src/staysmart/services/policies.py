from staysmart.domain.models import Amenity, HotelPolicyInfo
from staysmart.providers.base import HotelProvider


async def get_hotel_policies(provider: HotelProvider, hotel_id: str) -> HotelPolicyInfo:
    details = await provider.get_hotel_details(hotel_id)
    hotel = details.hotel
    pet_friendly = Amenity.PET_FRIENDLY in hotel.amenities
    information_gaps = ["check_in_time", "check_out_time"]
    if not pet_friendly:
        information_gaps.append("pet_policy")

    return HotelPolicyInfo(
        hotel_id=hotel.hotel_id,
        hotel_name=hotel.name,
        general_info=hotel.description,
        cancellation_policy=hotel.cancellation_policy,
        pet_policy="allowed" if pet_friendly else "unknown",
        pet_policy_source="amenities" if pet_friendly else "not_provided",
        check_in_time=None,
        check_out_time=None,
        information_gaps=information_gaps,
    )
