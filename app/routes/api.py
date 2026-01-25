from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from ..extensions import db
from ..models import Event, Booking

api_bp = Blueprint("api", __name__, url_prefix="/api")


def _iso(dt: Any) -> Optional[str]:
    """Return ISO8601 string for datetime-like values, or pass through strings."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _event_to_dict(event: Event) -> Dict[str, Any]:
    booked = Booking.query.filter_by(event_id=event.id).count()
    remaining = max(int(event.capacity) - booked, 0) if event.capacity is not None else None

    return {
        "id": event.id,
        "title": event.title,
        "description": event.description,
        "location": event.location,
        "start_time": _iso(event.start_time),
        "end_time": _iso(event.end_time),
        "capacity": event.capacity,
        "booked": booked,
        "remaining": remaining,
        "created_by": event.created_by,
        "created_at": _iso(event.created_at),
    }


def _booking_to_dict(booking: Booking) -> Dict[str, Any]:
    # ticket_code is optional (for later Cloud Function check-in feature)
    ticket_code = getattr(booking, "ticket_code", None)
    return {
        "id": booking.id,
        "user_id": booking.user_id,
        "event_id": booking.event_id,
        "ticket_code": ticket_code,
        "created_at": _iso(booking.created_at),
    }


def _is_admin() -> bool:
    return bool(getattr(current_user, "role", None) == "admin")


def _bad_request(msg: str):
    return jsonify({"error": "bad_request", "message": msg}), 400


def _forbidden(msg: str = "Forbidden"):
    return jsonify({"error": "forbidden", "message": msg}), 403


def _not_found(msg: str = "Not found"):
    return jsonify({"error": "not_found", "message": msg}), 404


@api_bp.get("/me")
def me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False}), 200

    return jsonify({
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "role": getattr(current_user, "role", "user"),
        }
    }), 200


@api_bp.get("/events")
def list_events():
    events = Event.query.order_by(Event.start_time.asc()).all()
    return jsonify({"events": [_event_to_dict(e) for e in events]}), 200


@api_bp.get("/events/<int:event_id>")
def event_detail(event_id: int):
    event = Event.query.get(event_id)
    if not event:
        return _not_found("Event not found")

    return jsonify({"event": _event_to_dict(event)}), 200


@api_bp.post("/events")
@login_required
def create_event():
    if not _is_admin():
        return _forbidden("Admin only")

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    location = (data.get("location") or "").strip()
    start_time = data.get("start_time")
    end_time = data.get("end_time")
    capacity = data.get("capacity")
    description = data.get("description")

    if not title:
        return _bad_request("title is required")
    if not location:
        return _bad_request("location is required")
    if not start_time:
        return _bad_request("start_time is required")
    if not end_time:
        return _bad_request("end_time is required")
    if capacity is None:
        return _bad_request("capacity is required")

    try:
        capacity_int = int(capacity)
        if capacity_int <= 0:
            return _bad_request("capacity must be > 0")
    except Exception:
        return _bad_request("capacity must be an integer")

    event = Event(
        title=title,
        description=description,
        location=location,
        start_time=start_time,
        end_time=end_time,
        capacity=capacity_int,
        created_by=current_user.id,
    )

    db.session.add(event)
    db.session.commit()

    return jsonify({"event": _event_to_dict(event)}), 201


@api_bp.post("/events/<int:event_id>/book")
@login_required
def book_event(event_id: int):
    event = Event.query.get(event_id)
    if not event:
        return _not_found("Event not found")

    # Prevent double booking
    existing = Booking.query.filter_by(event_id=event_id, user_id=current_user.id).first()
    if existing:
        return jsonify({"error": "conflict", "message": "Already booked", "booking": _booking_to_dict(existing)}), 409

    # Capacity check
    booked = Booking.query.filter_by(event_id=event_id).count()
    if event.capacity is not None and booked >= int(event.capacity):
        return jsonify({"error": "conflict", "message": "Event is full"}), 409

    booking = Booking(user_id=current_user.id, event_id=event_id)
    db.session.add(booking)
    db.session.commit()

    return jsonify({"booking": _booking_to_dict(booking)}), 201


@api_bp.get("/bookings")
@login_required
def my_bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()

    # Include event details for convenience
    event_ids = {b.event_id for b in bookings}
    events = Event.query.filter(Event.id.in_(event_ids)).all() if event_ids else []
    event_map = {e.id: _event_to_dict(e) for e in events}

    return jsonify({
        "bookings": [
            {
                **_booking_to_dict(b),
                "event": event_map.get(b.event_id),
            }
            for b in bookings
        ]
    }), 200
