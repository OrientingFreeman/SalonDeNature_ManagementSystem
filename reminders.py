from __future__ import annotations

from datetime import date, datetime, time

import click
from zoneinfo import ZoneInfo
from flask import current_app
from flask.cli import with_appcontext

from bookings.models import Booking
from dashboard.models import ShopSettings
from sms.service import send_booking_reminder_sms


def run_booking_reminders(target_date: date | None = None, source: str = "scheduler") -> dict:
    """Send same-day reminders for confirmed bookings on target_date.

    The default target is today in the Seoul business timezone. Booking datetimes in
    this project are stored as naive local values, so the query follows that convention.
    """
    seoul_today = datetime.now(ZoneInfo("Asia/Seoul")).date()
    reminder_date = target_date or seoul_today
    day_start = datetime.combine(reminder_date, time.min)
    day_end = datetime.combine(reminder_date, time.max)

    bookings = (
        Booking.query
        .filter(
            Booking.status == "confirmed",
            Booking.start_time >= day_start,
            Booking.start_time <= day_end,
        )
        .order_by(Booking.start_time.asc(), Booking.id.asc())
        .all()
    )

    summary = {
        "source": source,
        "reminder_date": reminder_date.isoformat(),
        "eligible": len(bookings),
        "customer_sent": 0,
        "customer_skipped": 0,
        "customer_failed": 0,
        "admin_sent": 0,
        "admin_skipped": 0,
        "admin_failed": 0,
        "bookings": [],
    }

    for booking in bookings:
        result = send_booking_reminder_sms(booking, reminder_date=reminder_date)
        customer_result = result.get("customer") or {}
        admin_results = result.get("admin") or []

        _count_result(summary, "customer", customer_result)
        for admin_result in admin_results:
            _count_result(summary, "admin", admin_result)

        summary["bookings"].append({
            "booking_id": booking.id,
            "start_time": booking.start_time.isoformat() if booking.start_time else None,
            "customer": customer_result,
            "admin": admin_results,
        })

    current_app.logger.info(
        "Booking reminder run complete. source=%s reminder_date=%s eligible=%s customer_sent=%s admin_sent=%s",
        source,
        reminder_date,
        summary["eligible"],
        summary["customer_sent"],
        summary["admin_sent"],
    )
    return summary


def _count_result(summary: dict, prefix: str, result: dict) -> None:
    if result.get("ok") and not result.get("skipped"):
        summary[f"{prefix}_sent"] += 1
    elif result.get("skipped"):
        summary[f"{prefix}_skipped"] += 1
    else:
        summary[f"{prefix}_failed"] += 1


@click.group("reminders")
def reminders_cli():
    """Booking reminder maintenance commands."""


@reminders_cli.command("run")
@click.option("--date", "target_date_text", help="Booking date to process (YYYY-MM-DD). Defaults to today in Asia/Seoul.")
@with_appcontext
def run_reminders_command(target_date_text):
    target_date = None
    if target_date_text:
        try:
            target_date = datetime.strptime(target_date_text, "%Y-%m-%d").date()
        except ValueError as exc:
            raise click.ClickException("--date must use YYYY-MM-DD format.") from exc

    result = run_booking_reminders(target_date=target_date, source="cli")
    click.echo(
        "Reminder run complete: "
        f"date={result['reminder_date']} eligible={result['eligible']} "
        f"customer(sent={result['customer_sent']}, skipped={result['customer_skipped']}, failed={result['customer_failed']}) "
        f"admin(sent={result['admin_sent']}, skipped={result['admin_skipped']}, failed={result['admin_failed']})"
    )
