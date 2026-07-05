from __future__ import annotations

DEFAULT_SMS_TEMPLATES = [
    {
        "template_key": "booking_created",
        "name": "예약 완료",
        "content": (
            "[{shop_name}] {customer_name}님, 예약이 접수되었습니다.\n"
            "- 시술: {service_name}\n"
            "- 담당: {staff_name}\n"
            "- 일시: {booking_datetime}"
        ),
        "description": "고객 예약이 새로 생성되었을 때 발송됩니다.",
        "sort_order": 10,
    },
    {
        "template_key": "booking_changed",
        "name": "예약 변경",
        "content": (
            "[{shop_name}] 예약 정보가 변경되었습니다.\n"
            "- 시술: {service_name}\n"
            "- 담당: {staff_name}\n"
            "- 변경 일시: {booking_datetime}"
        ),
        "description": "예약 일시, 담당자, 시술 정보가 변경되었을 때 발송됩니다.",
        "sort_order": 20,
    },
    {
        "template_key": "booking_cancelled",
        "name": "예약 취소",
        "content": (
            "[{shop_name}] 예약이 취소되었습니다.\n"
            "- 시술: {service_name}\n"
            "- 일시: {booking_datetime}"
        ),
        "description": "예약이 취소되었을 때 발송됩니다.",
        "sort_order": 30,
    },
    {
        "template_key": "deposit_request",
        "name": "예약금 입금 요청",
        "content": (
            "[{shop_name}] 예약금 입금 안내입니다.\n"
            "- 시술: {service_name}\n"
            "- 일시: {booking_datetime}\n"
            "- 예약금: {deposit_amount}\n"
            "- 입금계좌: {deposit_account}\n"
            "{deposit_notice}"
        ),
        "description": "관리자가 예약금 결제/입금 정보를 요청할 때 발송됩니다.",
        "sort_order": 40,
    },
    {
        "template_key": "deposit_paid",
        "name": "예약금 확인 완료",
        "content": (
            "[{shop_name}] 예약금 입금이 확인되었습니다.\n"
            "- 시술: {service_name}\n"
            "- 일시: {booking_datetime}"
        ),
        "description": "예약금 입금 확인 또는 결제 완료 처리 시 발송됩니다.",
        "sort_order": 50,
    },
]

SMS_PLACEHOLDERS = [
    ("{shop_name}", "매장명"),
    ("{customer_name}", "고객명"),
    ("{customer_phone}", "고객 전화번호"),
    ("{staff_name}", "담당자명"),
    ("{service_name}", "시술명"),
    ("{booking_date}", "예약일"),
    ("{booking_time}", "예약시간"),
    ("{booking_datetime}", "예약일시"),
    ("{deposit_amount}", "예약금"),
    ("{deposit_account}", "입금계좌"),
    ("{deposit_due_minutes}", "예약금 입금기한(분)"),
    ("{deposit_notice}", "예약금 안내문"),
    ("{payment_link}", "예약금 결제 링크"),
]
