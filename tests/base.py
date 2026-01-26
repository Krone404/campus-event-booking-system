import unittest
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import User, Event


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Seed users
            self.user = User(email="user@test.com", role="user")
            self.user.set_password("pass")

            self.admin = User(email="admin@test.com", role="admin")
            self.admin.set_password("pass")

            db.session.add_all([self.user, self.admin])
            db.session.commit()

            # Seed an event created by admin
            start = datetime.now(timezone.utc).replace(microsecond=0)
            end = start + timedelta(hours=1)

            event = Event(
                title="Seed Event",
                location="BU",
                start_time=start,
                end_time=end,
                capacity=5,
                created_by=self.admin.id,
            )
            db.session.add(event)
            db.session.commit()

            self.event_id = event.id

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def login_user(self):
        return self.client.post(
            "/auth/login",
            data={"email": "user@test.com", "password": "pass"},
            follow_redirects=True,
        )

    def login_admin(self):
        return self.client.post(
            "/auth/login",
            data={"email": "admin@test.com", "password": "pass"},
            follow_redirects=True,
        )

    def logout(self):
        return self.client.get("/auth/logout", follow_redirects=True)
