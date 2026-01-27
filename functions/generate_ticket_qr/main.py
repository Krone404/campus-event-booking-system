from __future__ import annotations

import base64
import io
import json
import os
from typing import Any, Dict, Tuple

import qrcode


def _json(status: int, payload: Dict[str, Any]) -> Tuple[str, int, Dict[str, str]]:
    return (json.dumps(payload), status, {"Content-Type": "application/json"})


def generate_ticket_qr(request):
    expected = os.environ.get("QR_FUNCTION_SECRET", "")
    provided = request.headers.get("X-QR-Secret", "")
    if not expected or provided != expected:
        return _json(401, {"error": "unauthorized"})

    data = request.get_json(silent=True) or {}
    ticket_code = (data.get("ticket_code") or "").strip()

    if not ticket_code:
        return _json(400, {"error": "bad_request", "message": "ticket_code is required"})

    img = qrcode.make(ticket_code)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return _json(200, {
        "ticket_code": ticket_code,
        "png_base64": png_b64,
        "data_url": f"data:image/png;base64,{png_b64}",
    })
