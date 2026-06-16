from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, session, current_app
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db
from customers.models import Customer

from translations import get_text, normalize_lang

import requests

def get_lang():
    lang = normalize_lang(request.args.get("lang", session.get("lang", "en")))
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
            return "가입되지 않은 연락처입니다.", 400

        if not check_password_hash(customer.password_hash, password):
            return "비밀번호가 일치하지 않습니다.", 400

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
        return "Kakao login failed.", 400

    token_response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": current_app.config["KAKAO_REST_API_KEY"],
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
        return f"Failed to get Kakao access token: {token_json}", 400

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