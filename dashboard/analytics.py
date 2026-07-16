from datetime import date, datetime, time, timedelta

from bookings.models import Booking


def build_revenue_analytics(start_date=None, end_date=None):
    today = date.today()
    filter_start_date = start_date or today.replace(day=1)
    filter_end_date = end_date or today
    if filter_start_date > filter_end_date:
        filter_start_date, filter_end_date = filter_end_date, filter_start_date

    filter_start = datetime.combine(filter_start_date, time.min)
    filter_end = datetime.combine(filter_end_date, time.max)
    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)
    week_start = datetime.combine(today - timedelta(days=today.weekday()), time.min)
    month_start = datetime.combine(today.replace(day=1), time.min)

    completed_bookings = Booking.query.filter(Booking.status == "completed").all()
    period_bookings = Booking.query.filter(
        Booking.start_time >= filter_start,
        Booking.start_time <= filter_end,
    ).order_by(Booking.start_time.asc()).all()
    filtered_bookings = [b for b in period_bookings if b.status == "completed"]

    def revenue(items):
        return sum((b.service.price or 0) for b in items if b.service)

    daily_revenue = {}
    staff_revenue, staff_count = {}, {}
    category_revenue, category_count = {}, {}
    service_revenue, service_count = {}, {}
    weekday_count = {name: 0 for name in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
    hour_count = {f"{hour:02d}:00": 0 for hour in range(9, 21)}

    for booking in filtered_bookings:
        day = booking.start_time.date().isoformat()
        daily_revenue.setdefault(day, {"count": 0, "revenue": 0})
        daily_revenue[day]["count"] += 1
        amount = booking.service.price or 0 if booking.service else 0
        daily_revenue[day]["revenue"] += amount
        staff_name = booking.staff.name if booking.staff else "Unassigned"
        category = booking.service.category if booking.service else "Unknown"
        service_name = booking.service.name_ko if booking.service else "Unknown"
        staff_revenue[staff_name] = staff_revenue.get(staff_name, 0) + amount
        staff_count[staff_name] = staff_count.get(staff_name, 0) + 1
        category_revenue[category] = category_revenue.get(category, 0) + amount
        category_count[category] = category_count.get(category, 0) + 1
        service_revenue[service_name] = service_revenue.get(service_name, 0) + amount
        service_count[service_name] = service_count.get(service_name, 0) + 1

    for booking in period_bookings:
        weekday_count[list(weekday_count.keys())[booking.start_time.weekday()]] += 1
        label = f"{booking.start_time.hour:02d}:00"
        if label in hour_count:
            hour_count[label] += 1

    status_order = ["pending", "confirmed", "completed", "cancelled", "no_show"]
    status_counts = {status: 0 for status in status_order}
    for booking in period_bookings:
        status_counts[booking.status] = status_counts.get(booking.status, 0) + 1

    total = len(period_bookings)
    cancelled = status_counts.get("cancelled", 0)
    no_show = status_counts.get("no_show", 0)
    terminal = status_counts.get("completed", 0) + cancelled + no_show
    filtered_revenue = revenue(filtered_bookings)

    customer_ids = {b.customer_id for b in filtered_bookings}
    new_customers = 0
    returning_customers = 0
    for customer_id in customer_ids:
        first_completed = Booking.query.filter(
            Booking.customer_id == customer_id,
            Booking.status == "completed",
        ).order_by(Booking.start_time.asc()).first()
        if first_completed and filter_start <= first_completed.start_time <= filter_end:
            new_customers += 1
        else:
            returning_customers += 1

    daily_revenue = dict(sorted(daily_revenue.items()))
    staff_revenue = dict(sorted(staff_revenue.items(), key=lambda x: x[1], reverse=True))
    category_revenue = dict(sorted(category_revenue.items(), key=lambda x: x[1], reverse=True))
    service_revenue = dict(sorted(service_revenue.items(), key=lambda x: x[1], reverse=True))

    return {
        "range": {"start_date": filter_start_date.isoformat(), "end_date": filter_end_date.isoformat()},
        "summary": {
            "today_revenue": revenue([b for b in completed_bookings if day_start <= b.start_time <= day_end]),
            "week_revenue": revenue([b for b in completed_bookings if b.start_time >= week_start]),
            "month_revenue": revenue([b for b in completed_bookings if b.start_time >= month_start]),
            "total_revenue": revenue(completed_bookings),
            "filtered_revenue": filtered_revenue,
            "average_ticket": round(filtered_revenue / len(filtered_bookings)) if filtered_bookings else 0,
            "completed_count": len(completed_bookings),
            "period_booking_count": total,
            "cancellation_rate": round(cancelled / total * 100, 1) if total else 0,
            "no_show_rate": round(no_show / total * 100, 1) if total else 0,
            "completion_rate": round(status_counts.get("completed", 0) / terminal * 100, 1) if terminal else 0,
            "new_customer_count": new_customers,
            "returning_customer_count": returning_customers,
            "repeat_customer_rate": round(returning_customers / len(customer_ids) * 100, 1) if customer_ids else 0,
        },
        "status_counts": status_counts,
        "daily_revenue": daily_revenue,
        "staff": [{"name": n, "completed_count": staff_count[n], "revenue": v} for n, v in staff_revenue.items()],
        "categories": [{"name": n, "completed_count": category_count[n], "revenue": v} for n, v in category_revenue.items()],
        "services": [{"name": n, "completed_count": service_count[n], "revenue": v} for n, v in service_revenue.items()],
        "weekday_counts": weekday_count,
        "hour_counts": hour_count,
    }
