from app import app
from extensions import db
from staff.models import StaffTimeOff

with app.app_context():
    db.create_all()
    print("staff_time_offs table is ready.")
