from flask import Flask, redirect, url_for
from .config import Config
from .extensions import db, login_manager
from .models import User

def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from .routes.events import events_bp
    app.register_blueprint(events_bp)

    @app.get("/")
    def home():
        return redirect(url_for("events.list_events"))

    @app.cli.command("init-db")
    def init_db():
        """Create tables if they don't exist."""
        with app.app_context():
            db.create_all()
        print("Database initialised.")

    return app
