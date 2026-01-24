from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import os

from google.cloud import firestore

_client: Optional[firestore.Client] = None

def _get_client() -> firestore.Client:
    global _client
    if _client is None:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
        _client = firestore.Client(project=project) if project else firestore.Client()
    return _client

def log_event(action: str, user_id: Optional[int] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    """
    Writes an audit log document to Firestore.
    Non-blocking enough for coursework; if Firestore fails, we swallow the error.
    """
    doc = {
        "action": action,
        "user_id": user_id,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _get_client().collection("logs").add(doc)
    except Exception:
        # Don't break core app if logging fails
        pass
