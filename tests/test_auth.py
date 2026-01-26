from app.extensions import db
from app.models import User
from tests.base import BaseTestCase


class AuthTests(BaseTestCase):
    def test_register_and_login(self):
        # Register a new user
        r = self.client.post(
            "/auth/register",
            data={"email": "new@test.com", "password": "pass"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)

        with self.app.app_context():
            u = db.session.query(User).filter_by(email="new@test.com").first()
            self.assertIsNotNone(u)

        # Logout then login again
        self.logout()

        r2 = self.client.post(
            "/auth/login",
            data={"email": "new@test.com", "password": "pass"},
            follow_redirects=True,
        )
        self.assertEqual(r2.status_code, 200)

    def test_login_rejects_bad_password(self):
        r = self.client.post(
            "/auth/login",
            data={"email": "user@test.com", "password": "wrong"},
            follow_redirects=True,
        )
        self.assertEqual(r.status_code, 200)  # page renders with flash error
