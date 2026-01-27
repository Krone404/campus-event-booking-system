from __future__ import annotations
import os
import json
from datetime import datetime
from typing import Any, Dict, Optional
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from ..services.logging_service import log_event
from ..extensions import db
from ..models import Event, Booking, User
from ..security import csrf
import uuid
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus




api_bp = Blueprint("api", __name__, url_prefix="/api")

def _parse_iso_dt(value: Any):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Supports "2026-02-01T10:00:00"
        return datetime.fromisoformat(value)
    raise ValueError("Invalid datetime format")

def _iso(dt: Any) -> Optional[str]:
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

def _id_token_for_audience(audience: str) -> str:
    # Works on Google-managed runtimes (App Engine / Cloud Run / Functions) via metadata server
    token_url = (
        "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
        f"?audience={quote_plus(audience)}&format=full"
    )
    req = urlrequest.Request(token_url, headers={"Metadata-Flavor": "Google"}, method="GET")
    with urlrequest.urlopen(req, timeout=5) as resp:
        return resp.read().decode("utf-8")

def _call_checkin_function(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = os.environ.get("CHECKIN_FUNCTION_URL")
    secret = os.environ.get("CHECKIN_FUNCTION_SECRET")

    if not url:
        raise RuntimeError("CHECKIN_FUNCTION_URL not set")
    if not secret:
        raise RuntimeError("CHECKIN_FUNCTION_SECRET not set")

    token = _id_token_for_audience(url)

    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Checkin-Secret": secret,
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Function HTTP {e.code}: {raw[:200]}")
    except URLError as e:
        raise RuntimeError(f"Function unreachable: {e}")

def _call_qr_function(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = os.environ.get("QR_FUNCTION_URL")
    secret = os.environ.get("QR_FUNCTION_SECRET")

    if not url:
        raise RuntimeError("QR_FUNCTION_URL not set")
    if not secret:
        raise RuntimeError("QR_FUNCTION_SECRET not set")

    token = _id_token_for_audience(url)

    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-QR-Secret": secret,
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"QR Function HTTP {e.code}: {raw[:200]}")
    except URLError as e:
        raise RuntimeError(f"QR Function unreachable: {e}")

def _call_email_function(payload: Dict[str, Any]) -> Dict[str, Any]:
    url = os.environ.get("EMAIL_FUNCTION_URL")
    secret = os.environ.get("EMAIL_FUNCTION_SECRET")

    if not url:
        raise RuntimeError("EMAIL_FUNCTION_URL not set")
    if not secret:
        raise RuntimeError("EMAIL_FUNCTION_SECRET not set")

    token = _id_token_for_audience(url)

    body = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url=url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Email-Secret": secret,
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    try:
        with urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Email Function HTTP {e.code}: {raw[:200]}")
    except URLError as e:
        raise RuntimeError(f"Email Function unreachable: {e}")

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

@csrf.exempt
@api_bp.post("/events")
@login_required
def create_event():
    if not _is_admin():
        return _forbidden("Admin only")

    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    location = (data.get("location") or "").strip()
    capacity = data.get("capacity")
    description = data.get("description")

    try:
        start_time = _parse_iso_dt(data.get("start_time"))
        end_time = _parse_iso_dt(data.get("end_time"))
    except Exception:
        return _bad_request("start_time/end_time must be ISO8601 (e.g. 2026-02-01T10:00:00)")


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

@csrf.exempt
@api_bp.post("/events/<int:event_id>/book")
@login_required
def book_event(event_id: int):
    event = db.session.get(Event, event_id)
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

    booking = Booking(
        user_id=current_user.id,
        event_id=event_id,
        ticket_code=str(uuid.uuid4())
    )

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

@csrf.exempt
@api_bp.post("/checkin/validate")
@login_required
def checkin_validate():
    data = request.get_json(silent=True) or {}
    ticket_code = (data.get("ticket_code") or "").strip()
    event_id = data.get("event_id")

    if not ticket_code or event_id is None:
        return _bad_request("ticket_code and event_id are required")

    try:
        result = _call_checkin_function({"ticket_code": ticket_code, "event_id": int(event_id)})
    except Exception as e:
        return jsonify({"error": "function_error", "message": str(e)}), 502

    return jsonify(result), 200

@api_bp.get("/bookings/ticket/<string:ticket_code>/qr")
@login_required
def booking_qr_by_ticket(ticket_code: str):
    ticket_code = (ticket_code or "").strip()
    if not ticket_code:
        return _bad_request("ticket_code is required")

    booking = Booking.query.filter_by(ticket_code=ticket_code).first()
    if not booking:
        return _not_found("Booking not found")

    if booking.user_id != current_user.id and not _is_admin():
        return _forbidden("Not allowed")

    try:
        result = _call_qr_function({"ticket_code": booking.ticket_code})
    except Exception as e:
        return jsonify({"error": "function_error", "message": str(e)}), 502

    return jsonify(result), 200

@api_bp.post("/bookings/<int:booking_id>/email")
@login_required
def email_booking_ticket(booking_id: int):
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return _not_found("Booking not found")

    if booking.user_id != current_user.id and not _is_admin():
        return _forbidden("Not allowed")

    # generate QR first
    try:
        qr = _call_qr_function({"ticket_code": booking.ticket_code})
    except Exception as e:
        return jsonify({"error": "qr_error", "message": str(e)}), 502

    # simple email body
    html = f"""
    <h1>Your booking</h1>
    <p>Event ID: {booking.event_id}</p>
    <p>Ticket code: <strong>{booking.ticket_code}</strong></p>
    <p>Your QR code is attached.</p>
    """

    # look up the user's email
    user = db.session.get(User, booking.user_id)
    if not user:
        return _not_found("User not found")

    try:
        result = _call_email_function({
            "to_email": user.email,
            "subject": "Your Campus Event Ticket",
            "html": html,
            "qr_png_base64": qr.get("png_base64", ""),
        })
    except Exception as e:
        return jsonify({"error": "email_error", "message": str(e)}), 502

    log_event(
        "ticket_email_sent",
        user_id=current_user.id,
        meta={
            "booking_id": booking.id,
            "event_id": booking.event_id,
            "ticket_code": booking.ticket_code,
            "to_email": user.email,
        },
    )

    return jsonify({"ok": True, "email_result": result}), 200
