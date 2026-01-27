from __future__ import annotations

import json
import os
from typing import Any, Dict, Tuple

import requests


def _json(status: int, payload: Dict[str, Any]) -> Tuple[str, int, Dict[str, str]]:
    return (json.dumps(payload), status, {"Content-Type": "application/json"})


def send_booking_email(request):
    expected = os.environ.get("EMAIL_FUNCTION_SECRET", "")
    provided = request.headers.get("X-Email-Secret", "")
    if not expected or provided != expected:
        return _json(401, {"error": "unauthorized"})

    api_key = os.environ.get("SENDGRID_API_KEY", "")
    from_email = os.environ.get("FROM_EMAIL", "")
    if not api_key or not from_email:
        return _json(500, {"error": "server_error", "message": "Missing SENDGRID_API_KEY or FROM_EMAIL"})

    data = request.get_json(silent=True) or {}
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "Booking confirmation").strip()
    html = (data.get("html") or "").strip()

    # Optional QR attachment
    qr_png_base64 = (data.get("qr_png_base64") or "").strip()

    if not to_email or not html:
        return _json(400, {"error": "bad_request", "message": "to_email and html are required"})

    payload: Dict[str, Any] = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": from_email},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }

    if qr_png_base64:
        payload["attachments"] = [{
            "content": qr_png_base64,
            "type": "image/png",
            "filename": "ticket-qr.png",
            "disposition": "attachment",
        }]

    resp = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )

    if resp.status_code >= 400:
        return _json(502, {"error": "send_failed", "status": resp.status_code, "body": resp.text[:200]})

    return _json(200, {"ok": True})
