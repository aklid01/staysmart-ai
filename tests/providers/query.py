from datetime import date

from staysmart.domain.models import HotelSearchQuery

CHECK_IN = date(2026, 12, 4)
CHECK_OUT = date(2026, 12, 7)


def make_query(**overrides):
    values = {
        "destination": "Kyoto",
        "check_in": CHECK_IN,
        "check_out": CHECK_OUT,
        "guests": 2,
        "rooms": 1,
        "currency": "USD",
    }
    values.update(overrides)
    return HotelSearchQuery(**values)
