from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import psycopg2
from google.cloud import firestore


def _json(status: int, payload: Dict[str, Any]) -> Tuple[str, int, Dict[str, str]]:
    return (json.dumps(payload), status, {"Content-Type": "application/json"})


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def _get_pg_conn():
    conn_name = _require_env("CLOUD_SQL_CONNECTION_NAME")
    db_name = _require_env("DB_NAME")
    db_user = _require_env("DB_USER")
    db_pass = _require_env("DB_PASS")

    # Cloud Functions (gen2) supports Cloud SQL via unix socket mount:
    # host=/cloudsql/<PROJECT:REGION:INSTANCE>
    return psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_pass,
        host=f"/cloudsql/{conn_name}",
        connect_timeout=5,
    )


def _fs_client() -> firestore.Client:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    db_name = os.environ.get("FIRESTORE_DB")
    if project and db_name:
        return firestore.Client(project=project, database=db_name)
    if db_name:
        return firestore.Client(database=db_name)
    if project:
        return firestore.Client(project=project)
    return firestore.Client()


def _log(action: str, meta: Optional[Dict[str, Any]] = None) -> None:
    if os.environ.get("DISABLE_FIRESTORE_LOGS") == "1":
        return
    doc = {
        "action": action,
        "meta": meta or {},
        "created_at": _utc_iso(),
        "source": "cloud_function",
    }
    try:
        _fs_client().collection("logs").add(doc)
    except Exception as e:
        print("Firestore logging failed:", repr(e))


def checkin_validate(request):
    # Shared-secret header
    expected = os.environ.get("CHECKIN_FUNCTION_SECRET", "")
    provided = request.headers.get("X-Checkin-Secret", "")
    if not expected or provided != expected:
        _log("checkin_denied", {"reason": "bad_secret"})
        return _json(401, {"error": "unauthorized"})

    data = request.get_json(silent=True) or {}
    ticket_code = (data.get("ticket_code") or "").strip()
    event_id = data.get("event_id")

    if not ticket_code or event_id is None:
        _log("checkin_bad_request", {"missing": True})
        return _json(400, {"error": "bad_request", "message": "ticket_code and event_id are required"})

    try:
        event_id_int = int(event_id)
        if event_id_int <= 0:
            raise ValueError
    except Exception:
        return _json(400, {"error": "bad_request", "message": "event_id must be a positive integer"})

    try:
        conn = _get_pg_conn()
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, event_id, ticket_code, created_at
                    FROM bookings
                    WHERE ticket_code = %s AND event_id = %s
                    LIMIT 1
                    """,
                    (ticket_code, event_id_int),
                )
                row = cur.fetchone()
    except Exception as e:
        _log("checkin_error", {"error": repr(e)})
        return _json(500, {"error": "server_error"})
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not row:
        _log("checkin_invalid", {"event_id": event_id_int})
        return _json(200, {"valid": False})

    booking = {
        "id": row[0],
        "user_id": row[1],
        "event_id": row[2],
        "ticket_code": row[3],
        "created_at": row[4].isoformat() if hasattr(row[4], "isoformat") else str(row[4]),
    }

    _log("checkin_valid", {"event_id": event_id_int, "booking_id": booking["id"]})
    return _json(200, {"valid": True, "booking": booking})
