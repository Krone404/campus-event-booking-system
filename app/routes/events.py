import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Event, Booking
from ..services.logging_service import log_event
from urllib.parse import quote_plus


events_bp = Blueprint("events", __name__, url_prefix="/events")


def parse_dt(value: str):
    # expects "YYYY-MM-DDTHH:MM" from <input type="datetime-local">
    return datetime.strptime(value, "%Y-%m-%dT%H:%M")


@events_bp.get("/")
def list_events():
    events = db.session.scalars(select(Event).order_by(Event.start_time.asc())).all()
    return render_template("events/list.html", events=events)


@events_bp.get("/new")
@login_required
def new_event():
    if current_user.role != "admin":
        flash("Admin only.", "error")
        return redirect(url_for("events.list_events"))

    maps_js_key = os.environ.get("MAPS_API_KEY", "").strip()
    return render_template("events/new.html", maps_js_key=maps_js_key)


@events_bp.post("/new")
@login_required
def new_event_post():
    if current_user.role != "admin":
        flash("Admin only.", "error")
        return redirect(url_for("events.list_events"))

    title = (request.form.get("title") or "").strip()
    location = (request.form.get("location") or "").strip()
    start_time_raw = request.form.get("start_time") or ""
    end_time_raw = request.form.get("end_time") or ""
    capacity_raw = request.form.get("capacity") or "0"
    description = (request.form.get("description") or "").strip()

    lat_raw = (request.form.get("lat") or "").strip()
    lng_raw = (request.form.get("lng") or "").strip()

    lat = None
    lng = None

    if not title or not location or not start_time_raw or not end_time_raw:
        flash("Missing required fields.", "error")
        return redirect(url_for("events.new_event"))

    try:
        capacity = int(capacity_raw)
        start_time = parse_dt(start_time_raw)
        end_time = parse_dt(end_time_raw)
    except ValueError:
        flash("Invalid date/time or capacity.", "error")
        return redirect(url_for("events.new_event"))

    if capacity <= 0:
        flash("Capacity must be > 0.", "error")
        return redirect(url_for("events.new_event"))

    if end_time <= start_time:
        flash("End time must be after start time.", "error")
        return redirect(url_for("events.new_event"))

    if lat_raw and lng_raw:
        try:
            lat = float(lat_raw)
            lng = float(lng_raw)
        except ValueError:
            flash("Invalid map coordinates.", "error")
            return redirect(url_for("events.new_event"))
    else:
        flash("Please pick a location on the map.", "error")
        return redirect(url_for("events.new_event"))

    event = Event(
        title=title,
        description=description or None,
        location=location,
        lat=lat,
        lng=lng,
        start_time=start_time,
        end_time=end_time,
        capacity=capacity,
        created_by=current_user.id,
    )
    db.session.add(event)
    db.session.commit()

    log_event("event_created", user_id=current_user.id, meta={"event_id": event.id, "title": event.title})

    flash("Event created.", "success")
    return redirect(url_for("events.list_events"))


@events_bp.post("/<int:event_id>/book")
@login_required
def book_event(event_id: int):
    event = db.session.get(Event, event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events.list_events"))

    booked = db.session.scalar(
        select(db.func.count(Booking.id)).where(Booking.event_id == event_id)
    )
    if booked >= event.capacity:
        flash("Event is full.", "error")
        return redirect(url_for("events.list_events"))

    booking = Booking(
        user_id=current_user.id,
        event_id=event_id,
        ticket_code=str(uuid.uuid4())
    )
    db.session.add(booking)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("You already booked this event.", "error")
        return redirect(url_for("events.list_events"))

    qr_url = (os.environ.get("QR_FUNCTION_URL") or "").strip()
    qr_secret = (os.environ.get("QR_FUNCTION_SECRET") or "").strip()
    email_url = (os.environ.get("EMAIL_FUNCTION_URL") or "").strip()
    email_secret = (os.environ.get("EMAIL_FUNCTION_SECRET") or "").strip()

    if qr_url and qr_secret and email_url and email_secret and current_user.email:
        try:
            qr_r = requests.post(
                qr_url,
                headers={"X-QR-Secret": qr_secret, "Content-Type": "application/json"},
                json={"ticket_code": booking.ticket_code},
                timeout=15,
            )
            qr_r.raise_for_status()
            qr_data = qr_r.json()
            qr_png_base64 = (qr_data.get("png_base64") or "").strip()

            if qr_png_base64:
                email_r = requests.post(
                    email_url,
                    headers={"X-Email-Secret": email_secret, "Content-Type": "application/json"},
                    json={
                        "to_email": current_user.email,
                        "subject": "Your Campus Event Ticket",
                        "html": (
                            f"<p>Thanks for booking <strong>{event.title}</strong>.</p>"
                            f"<p>Your ticket code is <strong>{booking.ticket_code}</strong>.</p>"
                            f"<p>Show the QR code at check-in.</p>"
                        ),
                        "qr_png_base64": qr_png_base64,
                    },
                    timeout=15,
                )
                email_r.raise_for_status()
        except Exception:
            pass

    log_event(
        "booking_created",
        user_id=current_user.id,
        meta={"event_id": event_id, "booking_id": booking.id, "ticket_code": booking.ticket_code}
    )

    flash("Booking confirmed.", "success")
    return redirect(url_for("events.list_events"))

@events_bp.get("/<int:event_id>")
def event_detail(event_id: int):
    event = db.session.get(Event, event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("events.list_events"))

    maps_js_key = os.environ.get("MAPS_API_KEY", "").strip()

    maps_embed_url = None
    if maps_js_key and event.location:
        q = quote_plus(event.location)
        maps_embed_url = f"https://www.google.com/maps/embed/v1/place?key={maps_js_key}&q={q}"

    return render_template(
        "events/detail.html",
        event=event,
        maps_js_key=maps_js_key,
        maps_embed_url=maps_embed_url,
    )

def _call_function(url: str, secret_header: str, secret_value: str, payload: dict) -> dict:
    r = requests.post(
        url,
        headers={secret_header: secret_value, "Content-Type": "application/json"},
        json=payload,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()