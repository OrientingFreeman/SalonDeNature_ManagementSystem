import unittest

from app import create_app


class AdminApiContractTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def test_admin_bookings_requires_login(self):
        response = self.client.get('/api/v1/admin/bookings')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()['error']['code'], 'ADMIN_AUTHENTICATION_REQUIRED')

    def test_admin_analytics_requires_login(self):
        response = self.client.get('/api/v1/admin/analytics/revenue')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
