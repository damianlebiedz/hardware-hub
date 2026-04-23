"""Rental API schema: timestamps must serialize as unambiguous UTC (Zulu) for clients."""

import datetime

from backend.schemas import RentalRead


def test_rental_read_json_timestamps_end_with_z() -> None:
    rented = datetime.datetime(2026, 4, 23, 14, 30, 0)
    returned = datetime.datetime(2026, 4, 24, 9, 0, 0)
    r = RentalRead(
        id=1,
        user_id=2,
        hardware_id=3,
        rented_at=rented,
        returned_at=returned,
    )
    data = r.model_dump(mode="json")
    assert data["rented_at"] == "2026-04-23T14:30:00Z"
    assert data["returned_at"] == "2026-04-24T09:00:00Z"


def test_rental_read_json_null_returned_at() -> None:
    r = RentalRead(
        id=1,
        user_id=2,
        hardware_id=3,
        rented_at=datetime.datetime(2026, 4, 23, 14, 30, 0),
        returned_at=None,
    )
    data = r.model_dump(mode="json")
    assert data["returned_at"] is None
