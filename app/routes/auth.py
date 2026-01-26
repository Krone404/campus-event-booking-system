from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from ..extensions import db
from ..models import User
from ..services.logging_service import log_event


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.get("/register")
def register():
    return render_template("auth/register.html")

@auth_bp.post("/register")
def register_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    if not email or not password:
        flash("Email and password are required.", "error")
        return redirect(url_for("auth.register"))

    existing = db.session.scalar(select(User).where(User.email == email))
    if existing:
        flash("That email is already registered.", "error")
        return redirect(url_for("auth.register"))

    user = User(email=email)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    login_user(user)
    log_event("user_registered", user_id=user.id, meta={"email": user.email})
    flash("Account created. You're logged in.", "success")
    return redirect(url_for("auth.me"))

@auth_bp.get("/login")
def login():
    return render_template("auth/login.html")

@auth_bp.post("/login")
def login_post():
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = db.session.scalar(select(User).where(User.email == email))
    if not user or not user.check_password(password):
        flash("Invalid email or password.", "error")
        return redirect(url_for("auth.login"))

    login_user(user)
    log_event("user_login", user_id=user.id)
    flash("Logged in.", "success")
    return redirect(url_for("auth.me"))

@auth_bp.get("/logout")
@login_required
def logout():
    logout_user()
    log_event("user_logout", user_id=current_user.id)
    flash("Logged out.", "success")
    return redirect(url_for("home"))

@auth_bp.get("/me")
@login_required
def me():
    return render_template("auth/me.html", db_uri=str(db.engine.url))
