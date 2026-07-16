import unittest

from app import create_app


class ApiV1ContractTests(unittest.TestCase):
    def setUp(self):
        app = create_app()
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_openapi_contains_customer_booking_routes(self):
        response = self.client.get("/api/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.get_json()["paths"]
        self.assertIn("/api/v1/me/bookings", paths)
        self.assertIn("/api/v1/me/bookings/{booking_id}/cancel", paths)
        self.assertIn("/api/v1/me/bookings/{booking_id}/reschedule", paths)

    def test_customer_booking_list_requires_login(self):
        response = self.client.get("/api/v1/me/bookings")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "AUTHENTICATION_REQUIRED",
        )

    def test_customer_booking_create_requires_login(self):
        response = self.client.post(
            "/api/v1/me/bookings",
            json={"service_id": 1, "staff_id": "any", "start_time": "2026-08-01T14:00"},
        )
        self.assertEqual(response.status_code, 401)

    def test_availability_requires_date_and_service(self):
        response = self.client.get("/api/v1/availability")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "MISSING_REQUIRED_QUERY_PARAMETERS",
        )


if __name__ == "__main__":
    unittest.main()
