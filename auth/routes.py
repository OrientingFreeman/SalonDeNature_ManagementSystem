from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from customers.models import Customer

from translations import get_text, normalize_lang

def get_lang():
    lang = normalize_lang(request.args.get("lang", session.get("lang", "ko")))
    session["lang"] = lang
    return lang

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        password = request.form["password"]

        existing_customer = Customer.query.filter_by(phone=phone).first()

        if existing_customer and existing_customer.password_hash:
            return "이미 가입된 연락처입니다.", 400

        if existing_customer:
            customer = existing_customer
            customer.name = name
            customer.password_hash = generate_password_hash(password)
            customer.login_provider = "local"
        else:
            customer = Customer(
                name=name,
                phone=phone,
                password_hash=generate_password_hash(password),
                login_provider="local"
            )
            db.session.add(customer)

        db.session.commit()

        session["customer_id"] = customer.id

        return redirect(
            url_for(
                "customer_booking.customer_home",
                lang=session.get("lang", "ko")
            )
        )

    lang = get_lang()
    return render_template("signup.html", lang=lang, text=get_text(lang))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = request.form["phone"]
        password = request.form["password"]

        customer = Customer.query.filter_by(phone=phone).first()

        if not customer or not customer.password_hash:
            return "가입되지 않은 연락처입니다.", 400

        if not check_password_hash(customer.password_hash, password):
            return "비밀번호가 일치하지 않습니다.", 400

        customer.last_login_at = datetime.utcnow()
        db.session.commit()

        session["customer_id"] = customer.id

        return redirect(url_for("customer_booking.customer_home", lang=session.get("lang", "ko")))

    lang = get_lang()
    return render_template("login.html", lang=lang, text=get_text(lang))


@auth_bp.route("/logout")
def logout():
    session.pop("customer_id", None)
    return redirect(url_for("customer_booking.customer_home", lang=session.get("lang", "ko")))
