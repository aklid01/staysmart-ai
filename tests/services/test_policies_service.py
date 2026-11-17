import pytest

from staysmart.domain.errors import UnknownHotelError
from staysmart.services.policies import get_hotel_policies


async def test_policies_derive_pet_allowance_from_the_amenity_list(provider):
    info = await get_hotel_policies(provider, "hotel-kyo-01")

    assert info.hotel_id == "hotel-kyo-01"
    assert info.hotel_name == "Gion Machiya Stay"
    assert info.general_info == "Restored machiya townhouse with breakfast service near Gion."
    assert info.pet_policy == "allowed"
    assert info.pet_policy_source == "amenities"
    assert info.data_source == "mock"
    assert info.is_live is False


async def test_policies_report_missing_pet_information_honestly(provider):
    info = await get_hotel_policies(provider, "hotel-lis-01")

    assert info.pet_policy == "unknown"
    assert info.pet_policy_source == "not_provided"


async def test_policies_embed_the_full_cancellation_policy(provider):
    info = await get_hotel_policies(provider, "hotel-kyo-01")

    assert info.cancellation_policy.policy_type == "partial"
    assert info.cancellation_policy.refundable is True
    assert info.cancellation_policy.free_cancellation_days == 5
    assert info.cancellation_policy.penalty_nights == 1
    assert info.cancellation_policy.description == (
        "Refundable until 5 days before check-in, less a one-night penalty."
    )


async def test_policies_never_invent_check_in_or_check_out_times(provider):
    info = await get_hotel_policies(provider, "hotel-kyo-01")

    assert info.check_in_time is None
    assert info.check_out_time is None
    assert info.information_gaps == ["check_in_time", "check_out_time"]


async def test_policies_list_pet_policy_as_a_gap_when_unknown(provider):
    info = await get_hotel_policies(provider, "hotel-lis-01")

    assert info.information_gaps == ["check_in_time", "check_out_time", "pet_policy"]
    assert info.cancellation_policy.policy_type == "free"


async def test_policies_propagate_unknown_hotel_error(provider):
    with pytest.raises(UnknownHotelError):
        await get_hotel_policies(provider, "hotel-xxx-99")
