from datetime import date, datetime, timezone
from decimal import Decimal

_PRODID = "-//Instalysis//Deals//EN"


def _escape_ics_text(value: str) -> str:
    """Escape a text value per RFC 5545 3.3.11 (backslash, comma, semicolon, newline)."""
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


def _format_utc(moment: datetime) -> str:
    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _format_date(day: date) -> str:
    return day.strftime("%Y%m%d")


def build_deal_ics(
    deal_id: int,
    title: str,
    brand_name: str,
    shoot_at: datetime | None,
    payment_due_date: date | None,
    payment_amount: Decimal | None,
    currency: str,
    now: datetime | None = None,
) -> str:
    """Build RFC 5545 .ics calendar text for a deal's shoot and/or payment due date.

    Emits one VEVENT per known date, each with a VALARM reminder. Raises
    ValueError if neither date is set, since an empty calendar file isn't a
    meaningful download.
    """
    if shoot_at is None and payment_due_date is None:
        raise ValueError("The deal has neither a shoot date nor a payment due date to export.")

    dtstamp = _format_utc(now if now is not None else datetime.now(timezone.utc))

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{_PRODID}",
    ]

    if shoot_at is not None:
        summary = _escape_ics_text(f"Shoot — {brand_name}: {title}")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:deal-{deal_id}-shoot@instalysis",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART:{_format_utc(shoot_at)}",
                f"SUMMARY:{summary}",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "TRIGGER:-PT1H",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    if payment_due_date is not None:
        if payment_amount is not None:
            summary = _escape_ics_text(
                f"Payment due — {brand_name}: {title} ({payment_amount} {currency})"
            )
        else:
            summary = _escape_ics_text(f"Payment due — {brand_name}: {title}")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:deal-{deal_id}-payment@instalysis",
                f"DTSTAMP:{dtstamp}",
                f"DTSTART;VALUE=DATE:{_format_date(payment_due_date)}",
                f"SUMMARY:{summary}",
                "BEGIN:VALARM",
                "ACTION:DISPLAY",
                "DESCRIPTION:Reminder",
                "TRIGGER:-P1D",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
