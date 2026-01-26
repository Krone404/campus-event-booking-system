from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import Event
from tests.base import BaseTestCase


class ApiTests(BaseTestCase):
    def test_list_events(self):
        r = self.client.get("/api/events")
        self.assertEqual(r.status_code, 200)

        data = r.get_json()
        self.assertIn("events", data)
        self.assertGreaterEqual(len(data["events"]), 1)

    def test_create_event_admin_only(self):
        # logged in as normal user
        self.login_user()

        start = datetime.now(timezone.utc).replace(microsecond=0)
        end = start + timedelta(hours=1)

        payload = {
            "title": "Nope",
            "location": "BU",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "capacity": 10,
            "description": "test",
        }

        r = self.client.post("/api/events", json=payload)
        self.assertEqual(r.status_code, 403)

    def test_create_event_admin_success(self):
        self.login_admin()

        start = datetime.now(timezone.utc).replace(microsecond=0)
        end = start + timedelta(hours=1)

        payload = {
            "title": "Admin Created",
            "location": "BU",
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "capacity": 10,
            "description": "test",
        }

        r = self.client.post("/api/events", json=payload)
        self.assertEqual(r.status_code, 201)

        data = r.get_json()
        self.assertIn("event", data)
        self.assertEqual(data["event"]["title"], "Admin Created")

        with self.app.app_context():
            created = db.session.query(Event).filter_by(title="Admin Created").first()
            self.assertIsNotNone(created)

    def test_api_booking_and_prevent_double_booking(self):
        self.login_user()

        r1 = self.client.post(f"/api/events/{self.event_id}/book")
        self.assertEqual(r1.status_code, 201)

        # second booking should conflict
        r2 = self.client.post(f"/api/events/{self.event_id}/book")
        self.assertEqual(r2.status_code, 409)

    def test_my_bookings_returns_event_details(self):
        self.login_user()

        r1 = self.client.post(f"/api/events/{self.event_id}/book")
        self.assertEqual(r1.status_code, 201)

        r2 = self.client.get("/api/bookings")
        self.assertEqual(r2.status_code, 200)

        data = r2.get_json()
        self.assertIn("bookings", data)
        self.assertGreaterEqual(len(data["bookings"]), 1)
        self.assertIn("event", data["bookings"][0])
        self.assertEqual(data["bookings"][0]["event"]["id"], self.event_id)
