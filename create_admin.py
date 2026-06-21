from app import app
from extensions import db
from dashboard.models import AdminUser
from werkzeug.security import generate_password_hash


def create_admin():
    username = "admin"
    password = "admin1234"

    existing = AdminUser.query.filter_by(username=username).first()

    if existing:
        print("Admin user already exists.")
        return

    admin = AdminUser(
        username=username,
        password_hash=generate_password_hash(password),
        is_active=True
    )

    db.session.add(admin)
    db.session.commit()

    print("Admin user created.")
    print(f"username: {username}")
    print(f"password: {password}")


if __name__ == "__main__":
    with app.app_context():
        create_admin()
