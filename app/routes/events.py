from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import select
from ..extensions import db
from ..models import Event, Booking
from ..services.logging_service import log_event

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
    return render_template("events/new.html")

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

    event = Event(
        title=title,
        description=description or None,
        location=location,
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

    # capacity check
    booked = db.session.scalar(
        select(db.func.count(Booking.id)).where(Booking.event_id == event_id)
    )
    if booked >= event.capacity:
        flash("Event is full.", "error")
        return redirect(url_for("events.list_events"))

    booking = Booking(user_id=current_user.id, event_id=event_id)
    db.session.add(booking)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("You already booked this event.", "error")
        return redirect(url_for("events.list_events"))

    log_event("booking_created", user_id=current_user.id, meta={"event_id": event_id})

    flash("Booking confirmed.", "success")
    return redirect(url_for("events.list_events"))
