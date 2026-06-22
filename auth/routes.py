from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app, flash
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from customers.models import Customer

from translations import get_text, normalize_lang

import requests
import os
from authlib.integrations.flask_client import OAuth

def get_lang():
    lang = normalize_lang(request.args.get("lang", session.get("lang", "en")))
    session["lang"] = lang
    return lang

auth_bp = Blueprint("auth", __name__)

oauth = OAuth()

google = oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url=
        "https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile"
    }
)

@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        password = request.form["password"]

        existing_customer = Customer.query.filter_by(phone=phone).first()



        if existing_customer and existing_customer.password_hash:
            flash("This phone number is already registered.")
            return redirect(url_for("auth.signup", lang=session.get("lang", "en")))

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
                lang=session.get("lang", "en")
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
            flash("No account found with this phone number.")
            return redirect(url_for("auth.login", lang=session.get("lang", "en")))

        if not check_password_hash(customer.password_hash, password):
            flash("Incorrect password.")
            return redirect(url_for("auth.login", lang=session.get("lang", "en")))

        customer.last_login_at = datetime.utcnow()
        db.session.commit()

        session["customer_id"] = customer.id

        return redirect(url_for("customer_booking.customer_home", lang=session.get("lang", "en")))

    lang = get_lang()
    return render_template("login.html", lang=lang, text=get_text(lang))


@auth_bp.route("/logout")
def logout():
    session.pop("customer_id", None)
    return redirect(url_for("customer_booking.customer_home", lang=session.get("lang", "en")))


@auth_bp.route("/kakao/login")
def kakao_login():
    kakao_auth_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={current_app.config['KAKAO_REST_API_KEY']}"
        f"&redirect_uri={current_app.config['KAKAO_REDIRECT_URI']}"
        "&response_type=code"
    )
    return redirect(kakao_auth_url)


@auth_bp.route("/kakao/callback")
def kakao_callback():
    code = request.args.get("code")

    if not code:
        flash("Kakao login failed. Please try again.")
        return redirect(url_for("auth.login", lang=session.get("lang", "en")))

    token_response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": current_app.config["KAKAO_REST_API_KEY"],
            "client_secret": current_app.config["KAKAO_CLIENT_SECRET"],
            "redirect_uri": current_app.config["KAKAO_REDIRECT_URI"],
            "code": code,
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
        },
    )

    token_json = token_response.json()
    access_token = token_json.get("access_token")

    if not access_token:
        flash("Kakao login failed. Please try again.")
        return redirect(url_for("auth.login", lang=session.get("lang", "en")))
    '''
    if not access_token:
        return {
            "status_code": token_response.status_code,
            "kakao_response": token_json,
            "sent_client_id": current_app.config["KAKAO_REST_API_KEY"],
            "sent_redirect_uri": current_app.config["KAKAO_REDIRECT_URI"],
            "received_code_prefix": code[:20],
        }, 400
    '''

    user_response = requests.get(
        "https://kapi.kakao.com/v2/user/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    user_json = user_response.json()

    kakao_id = str(user_json.get("id"))
    kakao_account = user_json.get("kakao_account", {})
    profile = kakao_account.get("profile", {})

    email = kakao_account.get("email")
    nickname = profile.get("nickname") or "Kakao User"

    customer = Customer.query.filter_by(
        login_provider="kakao",
        provider_user_id=kakao_id
    ).first()

    if not customer:
        customer = Customer(
            name=nickname,
            phone=f"kakao_{kakao_id}",
            email=email,
            social_provider="kakao",
            social_id=kakao_id,
            login_provider="kakao",
            provider_user_id=kakao_id,
            last_login_at=datetime.utcnow(),
        )
        db.session.add(customer)
    else:
        customer.name = nickname
        customer.email = email
        customer.last_login_at = datetime.utcnow()

    db.session.commit()

    session["customer_id"] = customer.id
    session["lang"] = session.get("lang", "en")

    return redirect(url_for("customer_booking.customer_home", lang=session["lang"]))

@auth_bp.route("/google/login")
def google_login():

    redirect_uri = current_app.config["GOOGLE_REDIRECT_URI"]

    return google.authorize_redirect(
        redirect_uri
    )

@auth_bp.route("/login/google/callback")
def google_callback():

    token = google.authorize_access_token()

    user_info = token.get("userinfo")

    google_id = user_info["sub"]
    email = user_info.get("email")
    name = user_info.get("name", "Google User")

    customer = Customer.query.filter_by(
        login_provider="google",
        provider_user_id=google_id
    ).first()

    if not customer:

        customer = Customer(
            name=name,
            phone=f"google_{google_id}",
            email=email,
            social_provider="google",
            social_id=google_id,
            login_provider="google",
            provider_user_id=google_id,
            last_login_at=datetime.utcnow(),
        )

        db.session.add(customer)

    else:

        customer.name = name
        customer.email = email
        customer.last_login_at = datetime.utcnow()

    db.session.commit()

    session["customer_id"] = customer.id

    return redirect(
        url_for(
            "customer_booking.customer_home",
            lang=session.get("lang", "en")
        )
    )


@auth_bp.route("/change-password", methods=["GET", "POST"])
def customer_change_password():
    if not session.get("customer_id"):
        return redirect(url_for("auth.login", lang=session.get("lang", "en")))

    customer = Customer.query.get(session["customer_id"])

    if not customer:
        session.pop("customer_id", None)
        flash("Please log in again.")
        return redirect(url_for("auth.login", lang=session.get("lang", "en")))

    if customer.login_provider != "local" or not customer.password_hash:
        flash("Password change is only available for accounts created with phone number and password.")
        return redirect(url_for("customer_booking.my_bookings", lang=session.get("lang", "en")))

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if not check_password_hash(customer.password_hash, current_password):
            flash("Current password is incorrect.")
            return redirect(url_for("auth.customer_change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.")
            return redirect(url_for("auth.customer_change_password"))

        if len(new_password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect(url_for("auth.customer_change_password"))

        customer.password_hash = generate_password_hash(new_password)
        db.session.commit()

        flash("Password updated successfully.")
        return redirect(url_for("customer_booking.my_bookings", lang=session.get("lang", "en")))

    return render_template("customer_change_password.html")
