from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Tuple

import requests


def _json(status: int, payload: Dict[str, Any]) -> Tuple[str, int, Dict[str, str]]:
    return (json.dumps(payload), status, {"Content-Type": "application/json"})


def send_booking_email(request):
    # Shared-secret header (same pattern as your other functions)
    expected = os.environ.get("EMAIL_FUNCTION_SECRET", "")
    provided = request.headers.get("X-Email-Secret", "")
    if not expected or provided != expected:
        return _json(401, {"error": "unauthorized"})

    data = request.get_json(silent=True) or {}
    to_email = (data.get("to_email") or "").strip()
    subject = (data.get("subject") or "").strip() or "Your Campus Event Ticket"
    html = (data.get("html") or "").strip() or "<p>Your ticket is attached.</p>"
    qr_png_base64 = (data.get("qr_png_base64") or "").strip()

    if not to_email:
        return _json(400, {"error": "bad_request", "message": "to_email is required"})
    if not qr_png_base64:
        return _json(400, {"error": "bad_request", "message": "qr_png_base64 is required"})

    api_key = os.environ.get("SENDGRID_API_KEY", "")
    SENDGRID_FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "")
    if not api_key:
        return _json(500, {"error": "server_error", "message": "SENDGRID_API_KEY not set"})
    if not from_email:
        return _json(500, {"error": "server_error", "message": "SENDGRID_FROM_EMAIL not set"})

    # Inline image: reference this in HTML as <img src="cid:ticketqr" />
    if "cid:ticketqr" not in html:
        html = html + '<p><img alt="Ticket QR" src="cid:ticketqr" /></p>'

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": SENDGRID_FROM_EMAIL},
        "subject": subject,
        "content": [
            {"type": "text/plain", "value": "Your ticket is attached (QR code)."},
            {"type": "text/html", "value": html},
        ],
        "attachments": [
            {
                "content": qr_png_base64,            # already base64
                "type": "image/png",
                "filename": "ticket-qr.png",
                "disposition": "attachment",
                "content_id": "ticketqr",            # matches cid:ticketqr
            }
        ],
    }

    r = requests.post(
        "https://api.sendgrid.com/v3/mail/send",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )

    # SendGrid returns 202 on accepted
    if r.status_code != 202:
        return _json(
            502,
            {
                "error": "sendgrid_error",
                "status": r.status_code,
                "message": r.text[:300],
            },
        )

    return _json(200, {"ok": True})
