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

import base64
import requests
import uuid
from datetime import datetime


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

    return app


app = create_app()



if __name__ == "__main__":
    app.run(debug=True)
