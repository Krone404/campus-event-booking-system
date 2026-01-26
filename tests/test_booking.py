import unittest
from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import User, Event, Booking


class BookingTests(unittest.TestCase):
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

            user = User(email="user@test.com", role="user")
            user.set_password("pass")

            admin = User(email="admin@test.com", role="admin")
            admin.set_password("pass")

            db.session.add_all([user, admin])
            db.session.commit()

            start = datetime.now(timezone.utc).replace(microsecond=0)
            end = start + timedelta(hours=1)

            event = Event(
                title="Bookable",
                location="BU",
                start_time=start,
                end_time=end,
                capacity=1,
                created_by=admin.id,
            )
            db.session.add(event)
            db.session.commit()

            self.event_id = event.id

    def tearDown(self):
        with self.app.app_context():
            db.drop_all()

    def _login_user(self):
        return self.client.post(
            "/auth/login",
            data={"email": "user@test.com", "password": "pass"},
            follow_redirects=True,
        )

    def test_double_booking_prevented(self):
        self._login_user()

        r1 = self.client.post(f"/events/{self.event_id}/book", follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

        r2 = self.client.post(f"/events/{self.event_id}/book", follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

        with self.app.app_context():
            count = db.session.query(Booking).filter_by(event_id=self.event_id).count()
            self.assertEqual(count, 1)

    def test_capacity_full_blocks_second_user(self):
        # user 1 books (fills capacity 1)
        self._login_user()
        r1 = self.client.post(f"/events/{self.event_id}/book", follow_redirects=True)
        self.assertEqual(r1.status_code, 200)

        # log out user 1
        self.client.get("/auth/logout", follow_redirects=True)

        # create + login user 2
        with self.app.app_context():
            user2 = User(email="user2@test.com", role="user")
            user2.set_password("pass")
            db.session.add(user2)
            db.session.commit()

        self.client.post(
            "/auth/login",
            data={"email": "user2@test.com", "password": "pass"},
            follow_redirects=True,
        )

        # user 2 tries to book -> should not create booking
        r2 = self.client.post(f"/events/{self.event_id}/book", follow_redirects=True)
        self.assertEqual(r2.status_code, 200)

        with self.app.app_context():
            total = db.session.query(Booking).filter_by(event_id=self.event_id).count()
            self.assertEqual(total, 1)
