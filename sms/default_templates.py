from __future__ import annotations

DEFAULT_SMS_TEMPLATES = [
    {
        "template_key": "booking_created",
        "name": "Booking Confirmed",
        "content": (
            "[{shop_name}]\n\n"
            "Hello {customer_name},\n\n"
            "Your booking has been confirmed.\n\n"
            "Service: {service_name}\n"
            "Staff: {staff_name}\n"
            "Date & Time: {booking_datetime}\n\n"
            "Thank you! We look forward to seeing you."
        ),
        "description": "Sent to the customer when a booking is created.",
        "sort_order": 10,
    },
    {
        "template_key": "booking_changed",
        "name": "Booking Updated",
        "content": (
            "[{shop_name}]\n\n"
            "Hello {customer_name},\n\n"
            "Your booking has been updated.\n\n"
            "Service: {service_name}\n"
            "Staff: {staff_name}\n"
            "New Date & Time: {booking_datetime}\n\n"
            "If you have any questions, please contact us.\n\n"
            "Thank you!"
        ),
        "description": "Sent to the customer when a booking has been rescheduled or changed.",
        "sort_order": 20,
    },
    {
        "template_key": "booking_cancelled",
        "name": "Booking Cancelled",
        "content": (
            "[{shop_name}]\n\n"
            "Hello {customer_name},\n\n"
            "Your booking has been cancelled.\n\n"
            "Service: {service_name}\n"
            "Original Date & Time: {booking_datetime}\n\n"
            "We hope to see you again soon."
        ),
        "description": "Sent to the customer when a booking has been cancelled.",
        "sort_order": 30,
    },
    {
        "template_key": "deposit_request",
        "name": "Deposit Request",
        "content": (
            "[{shop_name}]\n\n"
            "Hello {customer_name},\n\n"
            "To confirm your booking, please complete the deposit payment.\n\n"
            "Amount: {deposit_amount}\n"
            "Account: {deposit_account}\n\n"
            "{deposit_notice}\n\n"
            "Thank you."
        ),
        "description": "Sent to the customer when a deposit is required to confirm a booking.",
        "sort_order": 40,
    },
    {
        "template_key": "deposit_paid",
        "name": "Deposit Confirmed",
        "content": (
            "[{shop_name}]\n\n"
            "Hello {customer_name},\n\n"
            "Your deposit has been received.\n\n"
            "Your booking is now confirmed.\n\n"
            "Service: {service_name}\n"
            "Date & Time: {booking_datetime}\n\n"
            "We look forward to seeing you!"
        ),
        "description": "Sent to the customer after the deposit payment has been confirmed.",
        "sort_order": 50,
    },
    {
        "template_key": "admin_booking_created",
        "name": "Admin - New Booking",
        "content": (
            "[{shop_name} Admin]\n\n"
            "New booking\n\n"
            "Customer: {customer_name}\n"
            "Phone: {customer_phone}\n"
            "Service: {service_name}\n"
            "Staff: {staff_name}\n"
            "Date & Time: {booking_datetime}"
        ),
        "description": "Sent to admin recipients when a new booking is created.",
        "sort_order": 110,
    },
    {
        "template_key": "admin_booking_changed",
        "name": "Admin - Booking Updated",
        "content": (
            "[{shop_name} Admin]\n\n"
            "Booking updated\n\n"
            "Customer: {customer_name}\n"
            "Phone: {customer_phone}\n"
            "Service: {service_name}\n"
            "Staff: {staff_name}\n"
            "New Date & Time: {booking_datetime}"
        ),
        "description": "Sent to admin recipients when a booking is updated.",
        "sort_order": 120,
    },
    {
        "template_key": "admin_booking_cancelled",
        "name": "Admin - Booking Cancelled",
        "content": (
            "[{shop_name} Admin]\n\n"
            "Booking cancelled\n\n"
            "Customer: {customer_name}\n"
            "Phone: {customer_phone}\n"
            "Service: {service_name}\n"
            "Date & Time: {booking_datetime}"
        ),
        "description": "Sent to admin recipients when a booking is cancelled.",
        "sort_order": 130,
    },
    {
        "template_key": "admin_deposit_request",
        "name": "Admin - Deposit Requested",
        "content": (
            "[{shop_name} Admin]\n\n"
            "Deposit requested\n\n"
            "Customer: {customer_name}\n"
            "Phone: {customer_phone}\n"
            "Amount: {deposit_amount}\n"
            "Booking: {booking_datetime}"
        ),
        "description": "Sent to admin recipients when a deposit request is sent.",
        "sort_order": 140,
    },
    {
        "template_key": "admin_deposit_paid",
        "name": "Admin - Deposit Confirmed",
        "content": (
            "[{shop_name} Admin]\n\n"
            "Deposit confirmed\n\n"
            "Customer: {customer_name}\n"
            "Phone: {customer_phone}\n"
            "Amount: {deposit_amount}\n"
            "Booking: {booking_datetime}"
        ),
        "description": "Sent to admin recipients when a deposit is confirmed.",
        "sort_order": 150,
    },
]

SMS_PLACEHOLDERS = [
    ("{shop_name}", "Shop name"),
    ("{customer_name}", "Customer name"),
    ("{customer_phone}", "Customer phone number"),
    ("{staff_name}", "Staff name"),
    ("{service_name}", "Service name"),
    ("{booking_date}", "Booking date"),
    ("{booking_time}", "Booking time"),
    ("{booking_datetime}", "Booking date and time"),
    ("{deposit_amount}", "Deposit amount"),
    ("{deposit_account}", "Deposit bank account"),
    ("{deposit_due_minutes}", "Deposit due time in minutes"),
    ("{deposit_notice}", "Deposit notice"),
    ("{payment_link}", "Payment link"),
]
