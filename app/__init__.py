from flask import Flask, redirect, url_for
from typing import Optional, Dict, Any
from .config import Config
from .extensions import db, login_manager
from .models import User
from .security import csrf

def create_app(config_overrides: Optional[Dict[str, Any]] = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    if config_overrides:
        app.config.update(config_overrides)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))

    from .routes.auth import auth_bp
    app.register_blueprint(auth_bp)

    from .routes.events import events_bp
    app.register_blueprint(events_bp)

    from .routes.debug import debug_bp
    app.register_blueprint(debug_bp)

    from .routes.api import api_bp
    app.register_blueprint(api_bp)

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
