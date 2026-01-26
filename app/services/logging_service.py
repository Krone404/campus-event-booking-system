# app/services/logging_service.py
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
        db_name = os.environ.get("FIRESTORE_DB")  # e.g. "campus-events-fs"

        if project and db_name:
            _client = firestore.Client(project=project, database=db_name)
        elif db_name:
            _client = firestore.Client(database=db_name)
        elif project:
            _client = firestore.Client(project=project)
        else:
            _client = firestore.Client()

    return _client


def log_event(action: str, user_id: Optional[int] = None, meta: Optional[Dict[str, Any]] = None) -> None:
    # Disable external writes during unit tests
    if os.environ.get("TESTING") == "1":
        return

    doc = {
        "action": action,
        "user_id": user_id,
        "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _get_client().collection("logs").add(doc)
    except Exception as e:
        # Print so you can see failures in App Engine logs
        print("Firestore logging failed:", repr(e))
