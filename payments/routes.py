from datetime import datetime
import base64
import requests

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app

from extensions import db
from bookings.models import Booking, Payment, BookingEvent
from dashboard.notifications import notify_deposit_paid
from sms.service import send_deposit_paid_sms


payment_bp = Blueprint("payments", __name__, url_prefix="/payment")


@payment_bp.route("/checkout/<int:payment_id>")
def checkout(payment_id):
    if not session.get("customer_id"):
        return redirect(url_for("auth.login"))

    payment = Payment.query.get_or_404(payment_id)
    booking = payment.booking

    if booking.customer_id != session["customer_id"]:
        flash("You are not authorized to access this payment.")
        return redirect(url_for("customer_booking.customer_home"))

    if payment.status == "paid":
        return redirect(
            url_for(
                "customer_booking.customer_booking_success",
                booking_id=booking.id,
                lang=session.get("lang", "en")
            )
        )

    return render_template(
        "payment_checkout.html",
        payment=payment,
        booking=booking,
        toss_client_key=current_app.config.get("TOSS_CLIENT_KEY"),
        success_url="https://salondenature.shop/payment/success",
        fail_url="https://salondenature.shop/payment/fail",
        lang=session.get("lang", "en")
    )


@payment_bp.route("/success")
def success():
    if not session.get("customer_id"):
        return redirect(url_for("auth.login"))

    payment_key = request.args.get("paymentKey")
    order_id = request.args.get("orderId")
    amount = request.args.get("amount", type=int)

    if not payment_key or not order_id or not amount:
        return "Invalid payment response.", 400

    payment = Payment.query.filter_by(order_id=order_id).first()

    if not payment:
        return "Payment not found.", 404

    booking = payment.booking

    if booking.customer_id != session["customer_id"]:
        return "Unauthorized payment access.", 403

    if payment.status == "paid":
        return redirect(
            url_for(
                "customer_booking.customer_booking_success",
                booking_id=booking.id,
                lang=session.get("lang", "en")
            )
        )

    if payment.amount != amount:
        payment.status = "failed"
        payment.failed_reason = "Payment amount mismatch."
        booking.deposit_payment_status = "failed"

        db.session.add(
            BookingEvent(
                booking_id=booking.id,
                event_type="payment_failed",
                memo="Payment amount mismatch."
            )
        )
        db.session.commit()

        return "Payment amount mismatch.", 400

    secret_key = current_app.config.get("TOSS_SECRET_KEY")

    encoded_secret = base64.b64encode(
        f"{secret_key}:".encode("utf-8")
    ).decode("utf-8")

    response = requests.post(
        "https://api.tosspayments.com/v1/payments/confirm",
        headers={
            "Authorization": f"Basic {encoded_secret}",
            "Content-Type": "application/json"
        },
        json={
            "paymentKey": payment_key,
            "orderId": order_id,
            "amount": amount
        },
        timeout=10
    )

    if response.status_code != 200:
        payment.status = "failed"
        payment.payment_key = payment_key
        payment.failed_reason = response.text
        booking.deposit_payment_status = "failed"

        db.session.add(
            BookingEvent(
                booking_id=booking.id,
                event_type="payment_failed",
                memo=response.text[:500]
            )
        )
        db.session.commit()

        return redirect(url_for("payments.fail"))

    toss_data = response.json()

    payment.payment_key = payment_key
    payment.status = "paid"
    payment.method = toss_data.get("method")
    payment.paid_at = datetime.utcnow()

    booking.deposit_paid = True
    booking.deposit_payment_status = "paid"
    booking.status = "confirmed"

    db.session.add(
        BookingEvent(
            booking_id=booking.id,
            event_type="payment_paid",
            memo=f"Toss payment confirmed. order_id={order_id}"
        )
    )
    notify_deposit_paid(booking, source="Toss payment")
    send_deposit_paid_sms(booking)

    db.session.commit()

    return redirect(
        url_for(
            "customer_booking.customer_booking_success",
            booking_id=booking.id,
            lang=session.get("lang", "en")
        )
    )


@payment_bp.route("/fail")
def fail():
    return render_template(
        "payment_fail.html",
        lang=session.get("lang", "en")
    )