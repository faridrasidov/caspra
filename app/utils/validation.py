from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pycountry


def iso_currency(value: str) -> str:
    if not isinstance(value, str) or pycountry.currencies.get(alpha_3=value.upper()) is None:
        raise ValueError("Use a supported ISO currency")
    return value.upper()


def timezone_name(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Use an IANA timezone name")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("Use an IANA timezone name") from exc
    return value
