from datetime import time

from app import app
from extensions import db

from customers.models import Customer
from staff.models import Staff, StaffSchedule
from bookings.models import Service, StaffService, Booking, BookingEvent

from dashboard.models import ShopSettings

from werkzeug.security import generate_password_hash
from dashboard.models import AdminUser

def reset_db():
    db.drop_all()
    db.create_all()


def create_customers():
    customer = Customer(
        name="John Smith",
        phone="+1-555-123-4567",
        email="john@example.com",
        social_provider="google",
        social_id="google-test-001",
        no_show_count=0,
        booking_restricted=False,
        memo="Test customer"
    )

    db.session.add(customer)
    db.session.commit()

    return customer

def create_staff():
    staff_a = Staff(
        name="Staff A",
        role="staff",
        phone="010-1111-2222",
        is_active=True
    )

    staff_b = Staff(
        name="Staff B",
        role="staff",
        phone="010-3333-4444",
        is_active=True
    )

    db.session.add_all([staff_a, staff_b])
    db.session.commit()

    return staff_a, staff_b


def create_services():
    basic_nail = Service(
        category="nail",
        name_ko="기본 네일",
        name_en="Basic Nail",
        duration_minutes=60,
        price=50000,
        deposit_required=False,
        deposit_amount=0,
        is_active=True
    )

    gel_art = Service(
        category="nail",
        name_ko="젤아트",
        name_en="Gel Art",
        duration_minutes=90,
        price=80000,
        deposit_required=True,
        deposit_amount=10000,
        is_active=True
    )

    waxing = Service(
        category="waxing",
        name_ko="왁싱",
        name_en="Waxing",
        duration_minutes=30,
        price=40000,
        deposit_required=False,
        deposit_amount=0,
        is_active=True
    )

    db.session.add_all([basic_nail, gel_art, waxing])
    db.session.commit()

    return basic_nail, gel_art, waxing


def create_staff_schedules(staff_a, staff_b):
    schedules = []

    # 월~금: 0~4
    for day in range(0, 5):
        schedules.append(
            StaffSchedule(
                staff_id=staff_a.id,
                day_of_week=day,
                start_time=time(10, 0),
                end_time=time(19, 0),
                break_start_time=time(13, 0),
                break_end_time=time(14, 0),
                is_working=True
            )
        )

        schedules.append(
            StaffSchedule(
                staff_id=staff_b.id,
                day_of_week=day,
                start_time=time(11, 0),
                end_time=time(20, 0),
                break_start_time=time(14, 0),
                break_end_time=time(15, 0),
                is_working=True
            )
        )

    db.session.add_all(schedules)
    db.session.commit()


def create_staff_services(staff_a, staff_b, basic_nail, gel_art, waxing):
    staff_services = [
        StaffService(staff_id=staff_a.id, service_id=basic_nail.id),
        StaffService(staff_id=staff_a.id, service_id=gel_art.id),

        StaffService(staff_id=staff_b.id, service_id=basic_nail.id),
        StaffService(staff_id=staff_b.id, service_id=waxing.id),
    ]

    db.session.add_all(staff_services)
    db.session.commit()


def create_shop_settings():
    settings = ShopSettings(
        no_show_limit_count=3,
        same_day_cancel_block_enabled=True,
        deposit_enabled=False,
        booking_approval_mode="auto"
    )

    db.session.add(settings)
    db.session.commit()

    return settings

def create_admin_user():
    admin = AdminUser(
        username="admin",
        password_hash=generate_password_hash("admin1234"),
        is_active=True
    )

    db.session.add(admin)
    db.session.commit()

    return admin

def seed():
    reset_db()

    staff_a, staff_b = create_staff()
    basic_nail, gel_art, waxing = create_services()
    customer = create_customers()

    create_staff_schedules(staff_a, staff_b)
    create_staff_services(staff_a, staff_b, basic_nail, gel_art, waxing)

    settings = create_shop_settings()

    admin = create_admin_user()

    print("Seed data created successfully.")
    print(f"Staff A ID: {staff_a.id}")
    print(f"Staff B ID: {staff_b.id}")
    print(f"Basic Nail ID: {basic_nail.id}")
    print(f"Gel Art ID: {gel_art.id}")
    print(f"Waxing ID: {waxing.id}")
    print(f"Customer ID: {customer.id}")
    print(f"No-show limit count: {settings.no_show_limit_count}")
    print(f"Admin username: {admin.username}")
    print("Admin password: admin1234")




if __name__ == "__main__":
    with app.app_context():
        seed()
