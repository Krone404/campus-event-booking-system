from flask import Blueprint, jsonify
from flask_login import current_user
from ..services.logging_service import log_event

debug_bp = Blueprint("debug", __name__, url_prefix="/debug")

@debug_bp.get("/firestore")
def firestore_test():
    uid = current_user.id if current_user.is_authenticated else None
    log_event("firestore_test", user_id=uid, meta={"source": "debug_route"})
    return jsonify({"ok": True, "message": "Wrote firestore_test to logs"})
