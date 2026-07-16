from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import joinedload

from bookings.models import Booking
from customers.models import Customer


TERMINAL_STATUSES = {"completed", "cancelled", "no_show"}
ACTIVE_STATUSES = {"pending", "confirmed"}


def _percent(numerator, denominator):
    return round((numerator / denominator) * 100, 1) if denominator else 0.0


SEGMENT_LABELS = {
    "vip": "VIP",
    "at_risk": "At risk",
    "dormant": "Dormant",
    "potential_vip": "Potential VIP",
    "returning": "Returning",
    "new": "New",
}


def _segment_for(
    completed_count,
    total_revenue,
    last_visit_at,
    next_booking_at,
    cancellation_rate,
    no_show_rate,
    booking_restricted,
    today,
):
    """Return one mutually exclusive CRM segment and a factual reason.

    Precedence intentionally protects VIP classification first, then surfaces
    operational risk before lifecycle/value segments.
    """
    dormant_cutoff = datetime.combine(today - timedelta(days=90), time.min)
    recent_cutoff = datetime.combine(today - timedelta(days=60), time.min)

    if completed_count >= 5 or total_revenue >= 300000:
        reason = (
            f"{completed_count} completed visits"
            if completed_count >= 5
            else f"KRW {total_revenue:,} completed-booking revenue"
        )
        return "vip", reason

    if booking_restricted or no_show_rate >= 20 or cancellation_rate >= 40:
        if booking_restricted:
            reason = "Booking is restricted"
        elif no_show_rate >= 20:
            reason = f"No-show rate {no_show_rate}%"
        else:
            reason = f"Cancellation rate {cancellation_rate}%"
        return "at_risk", reason

    if last_visit_at and last_visit_at < dormant_cutoff and not next_booking_at:
        return "dormant", "No completed visit for more than 90 days and no upcoming booking"

    if (
        completed_count >= 3
        or total_revenue >= 180000
        or (
            completed_count >= 2
            and last_visit_at
            and last_visit_at >= recent_cutoff
            and next_booking_at
        )
    ):
        if completed_count >= 3:
            reason = f"{completed_count} completed visits"
        elif total_revenue >= 180000:
            reason = f"KRW {total_revenue:,} completed-booking revenue"
        else:
            reason = "Recent repeat customer with an upcoming booking"
        return "potential_vip", reason

    if completed_count >= 2:
        return "returning", f"{completed_count} completed visits"

    return "new", "Fewer than two completed visits"


def build_customer_crm_rows(today=None):
    today = today or date.today()
    now = datetime.now()

    customers = Customer.query.order_by(Customer.id.asc()).all()
    bookings = (
        Booking.query
        .options(joinedload(Booking.service), joinedload(Booking.staff))
        .order_by(Booking.start_time.asc())
        .all()
    )

    bookings_by_customer = defaultdict(list)
    for booking in bookings:
        bookings_by_customer[booking.customer_id].append(booking)

    rows = []
    for customer in customers:
        customer_bookings = bookings_by_customer.get(customer.id, [])
        completed = [b for b in customer_bookings if b.status == "completed"]
        cancelled = [b for b in customer_bookings if b.status == "cancelled"]
        no_show = [b for b in customer_bookings if b.status == "no_show"]
        upcoming = [
            b for b in customer_bookings
            if b.status in ACTIVE_STATUSES and b.start_time >= now
        ]

        completed_count = len(completed)
        total_revenue = sum((b.service.price if b.service else 0) for b in completed)
        last_visit_at = max((b.start_time for b in completed), default=None)
        next_booking_at = min((b.start_time for b in upcoming), default=None)
        terminal_count = completed_count + len(cancelled) + len(no_show)
        cancellation_rate = _percent(len(cancelled), terminal_count)
        no_show_rate = _percent(len(no_show), terminal_count)
        segment, segment_reason = _segment_for(
            completed_count,
            total_revenue,
            last_visit_at,
            next_booking_at,
            cancellation_rate,
            no_show_rate,
            customer.booking_restricted,
            today,
        )

        service_counts = Counter(
            b.service.name_ko for b in completed if b.service
        )
        staff_counts = Counter(
            b.staff.name for b in completed if b.staff
        )

        rows.append({
            "customer": customer,
            "booking_count": len(customer_bookings),
            "completed_count": completed_count,
            "total_revenue": total_revenue,
            "average_ticket": round(total_revenue / completed_count) if completed_count else 0,
            "last_visit_at": last_visit_at,
            "next_booking_at": next_booking_at,
            "cancelled_count": len(cancelled),
            "no_show_count": len(no_show),
            "cancellation_rate": cancellation_rate,
            "no_show_rate": no_show_rate,
            "preferred_service": service_counts.most_common(1)[0][0] if service_counts else None,
            "preferred_staff": staff_counts.most_common(1)[0][0] if staff_counts else None,
            "segment": segment,
            "segment_label": SEGMENT_LABELS[segment],
            "segment_reason": segment_reason,
        })

    return rows


def filter_customer_crm_rows(rows, query="", segment="all", status="all"):
    query = (query or "").strip().lower()
    filtered = []

    for row in rows:
        customer = row["customer"]
        haystack = " ".join([
            customer.name or "",
            customer.phone or "",
            customer.email or "",
        ]).lower()

        if query and query not in haystack:
            continue
        if segment != "all" and row["segment"] != segment:
            continue
        if status == "restricted" and not customer.booking_restricted:
            continue
        if status == "normal" and customer.booking_restricted:
            continue
        filtered.append(row)

    return filtered


def sort_customer_crm_rows(rows, sort_key="recent"):
    if sort_key == "revenue":
        return sorted(rows, key=lambda r: (r["total_revenue"], r["completed_count"]), reverse=True)
    if sort_key == "visits":
        return sorted(rows, key=lambda r: (r["completed_count"], r["total_revenue"]), reverse=True)
    if sort_key == "no_show":
        return sorted(rows, key=lambda r: (r["no_show_count"], r["no_show_rate"]), reverse=True)
    if sort_key == "risk":
        priority = {"at_risk": 5, "dormant": 4, "new": 3, "returning": 2, "potential_vip": 1, "vip": 0}
        return sorted(
            rows,
            key=lambda r: (priority.get(r["segment"], 0), r["no_show_rate"], r["cancellation_rate"]),
            reverse=True,
        )
    if sort_key == "name":
        return sorted(rows, key=lambda r: (r["customer"].name or "").lower())

    return sorted(
        rows,
        key=lambda r: r["last_visit_at"] or datetime.min,
        reverse=True,
    )


def summarize_customer_crm(rows):
    total_revenue = sum(row["total_revenue"] for row in rows)
    completed_visits = sum(row["completed_count"] for row in rows)
    return {
        "customer_count": len(rows),
        "vip_count": sum(1 for row in rows if row["segment"] == "vip"),
        "potential_vip_count": sum(1 for row in rows if row["segment"] == "potential_vip"),
        "returning_count": sum(1 for row in rows if row["segment"] in {"returning", "potential_vip", "vip"}),
        "at_risk_count": sum(1 for row in rows if row["segment"] == "at_risk"),
        "dormant_count": sum(1 for row in rows if row["segment"] == "dormant"),
        "restricted_count": sum(1 for row in rows if row["customer"].booking_restricted),
        "completed_visits": completed_visits,
        "total_revenue": total_revenue,
        "average_customer_value": round(total_revenue / len(rows)) if rows else 0,
    }


def build_customer_crm_detail(customer, bookings, today=None):
    today = today or date.today()
    now = datetime.now()
    bookings = list(bookings)
    completed = sorted(
        [b for b in bookings if b.status == "completed"],
        key=lambda b: b.start_time,
    )
    cancelled = [b for b in bookings if b.status == "cancelled"]
    no_show = [b for b in bookings if b.status == "no_show"]
    upcoming = [
        b for b in bookings
        if b.status in ACTIVE_STATUSES and b.start_time >= now
    ]

    completed_count = len(completed)
    total_revenue = sum((b.service.price if b.service else 0) for b in completed)
    last_visit_at = completed[-1].start_time if completed else None
    next_booking_at = min((b.start_time for b in upcoming), default=None)
    terminal_count = completed_count + len(cancelled) + len(no_show)

    service_counts = Counter(
        b.service.name_ko for b in completed if b.service
    )
    staff_counts = Counter(
        b.staff.name for b in completed if b.staff
    )
    hour_counts = Counter(b.start_time.hour for b in completed)

    visit_intervals = [
        (completed[index].start_time.date() - completed[index - 1].start_time.date()).days
        for index in range(1, len(completed))
        if completed[index].start_time.date() > completed[index - 1].start_time.date()
    ]
    average_visit_cycle_days = (
        round(sum(visit_intervals) / len(visit_intervals)) if visit_intervals else None
    )

    preferred_hour = None
    preferred_hour_share = 0.0
    if hour_counts:
        preferred_hour, preferred_hour_count = hour_counts.most_common(1)[0]
        preferred_hour_share = _percent(preferred_hour_count, completed_count)

    cancellation_rate = _percent(len(cancelled), terminal_count)
    no_show_rate = _percent(len(no_show), terminal_count)
    risk_score = no_show_rate * 2 + cancellation_rate
    if customer.booking_restricted or no_show_rate >= 30 or risk_score >= 50:
        risk_level = "high"
    elif no_show_rate > 0 or cancellation_rate >= 20:
        risk_level = "medium"
    else:
        risk_level = "low"

    segment, segment_reason = _segment_for(
        completed_count,
        total_revenue,
        last_visit_at,
        next_booking_at,
        cancellation_rate,
        no_show_rate,
        customer.booking_restricted,
        today,
    )

    return {
        "segment": segment,
        "segment_label": SEGMENT_LABELS[segment],
        "segment_reason": segment_reason,
        "booking_count": len(bookings),
        "completed_count": completed_count,
        "total_revenue": total_revenue,
        "average_ticket": round(total_revenue / completed_count) if completed_count else 0,
        "last_visit_at": last_visit_at,
        "next_booking_at": next_booking_at,
        "cancelled_count": len(cancelled),
        "no_show_count": len(no_show),
        "cancellation_rate": cancellation_rate,
        "no_show_rate": no_show_rate,
        "preferred_service": service_counts.most_common(1)[0][0] if service_counts else None,
        "preferred_service_count": service_counts.most_common(1)[0][1] if service_counts else 0,
        "preferred_staff": staff_counts.most_common(1)[0][0] if staff_counts else None,
        "preferred_staff_count": staff_counts.most_common(1)[0][1] if staff_counts else 0,
        "average_visit_cycle_days": average_visit_cycle_days,
        "preferred_hour": preferred_hour,
        "preferred_hour_share": preferred_hour_share,
        "risk_level": risk_level,
    }
