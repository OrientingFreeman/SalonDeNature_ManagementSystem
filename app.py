from flask import Flask
from config import Config
from extensions import db, migrate

import models
from dashboard.routes import dashboard_bp
from bookings.routes import booking_bp
from bookings.customer_routes import customer_booking_bp
from auth.routes import auth_bp, oauth
from staff.routes import staff_bp
from payments.routes import payment_bp
from reminders import reminders_cli
from api import api_v1_bp, api_docs_bp
from api.security import register_api_security



def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    oauth.init_app(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(customer_booking_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(staff_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(api_v1_bp)
    app.register_blueprint(api_docs_bp)
    register_api_security(app)
    app.cli.add_command(reminders_cli)

    return app


app = create_app()



if __name__ == "__main__":
    app.run(debug=True)
