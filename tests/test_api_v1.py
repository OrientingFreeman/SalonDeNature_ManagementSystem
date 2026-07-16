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
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["api_version"], "v1")

    def test_openapi_document(self):
        response = self.client.get("/api/openapi.json")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["openapi"], "3.0.3")
        self.assertIn("/api/v1/availability", payload["paths"])

    def test_availability_requires_date_and_service(self):
        response = self.client.get("/api/v1/availability")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertFalse(payload["success"])
        self.assertEqual(
            payload["error"]["code"],
            "MISSING_REQUIRED_QUERY_PARAMETERS",
        )

    def test_availability_rejects_bad_date(self):
        response = self.client.get(
            "/api/v1/availability?date=2026-99-99&service_id=1"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["error"]["code"],
            "INVALID_DATE_FORMAT",
        )


if __name__ == "__main__":
    unittest.main()
