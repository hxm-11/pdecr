from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class SignatureSchedule:
    target_close_date: str
    first_signature_date: str
    second_signature_date: str
    first_signature_lead_business_days: int = 10
    second_signature_lead_business_days: int = 5


def _parse_date(value: str) -> date:
    text = str(value or "").strip()
    if not text:
        raise ValueError("target_close_date is required")

    try:
        return date.fromisoformat(text)
    except ValueError:
        parsed = datetime.strptime(text, "%Y-%m-%d")
        return parsed.date()


def subtract_business_days(start: date, days: int) -> date:
    current = start
    remaining = max(0, int(days))
    while remaining:
        current -= timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def compute_signature_schedule(target_close_date: str) -> SignatureSchedule:
    target = _parse_date(target_close_date)
    return SignatureSchedule(
        target_close_date=target.isoformat(),
        first_signature_date=subtract_business_days(target, 10).isoformat(),
        second_signature_date=subtract_business_days(target, 5).isoformat(),
    )
