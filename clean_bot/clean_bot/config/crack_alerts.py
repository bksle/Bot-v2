"""Discord crack-trap alert channel + HTTP ingest."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

logger = logging.getLogger(__name__)


def get_alert_channel_id() -> int | None:
    raw = os.environ.get("CRACK_ALERT_CHANNEL_ID", "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def get_trap_listen_host() -> str:
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("PORT"):
        return os.environ.get("CRACK_ALERT_HOST", "0.0.0.0").strip() or "0.0.0.0"
    return os.environ.get("CRACK_ALERT_HOST", "127.0.0.1").strip() or "127.0.0.1"


def get_trap_listen_port() -> int:
    railway_port = os.environ.get("PORT", "").strip()
    if railway_port:
        try:
            return int(railway_port)
        except ValueError:
            pass
    raw = os.environ.get("CRACK_ALERT_PORT", "8799").strip()
    try:
        return int(raw)
    except ValueError:
        return 8799


def get_trap_secret() -> str:
    explicit = os.environ.get("CRACK_ALERT_SECRET", "").strip()
    if explicit:
        return explicit
    client_id = os.environ.get("CRACK_ALERT_APP_CLIENT_ID", "3so7Y4an8b").strip()
    client_secret = os.environ.get("CRACK_ALERT_APP_CLIENT_SECRET", "").strip()
    if not client_secret:
        return ""
    app_version = os.environ.get("CRACK_ALERT_APP_VERSION", "1.3").strip()
    service = os.environ.get("CRACK_ALERT_APP_SERVICE", "auto-snap-cloud-oauth").strip()
    material = f"{client_id}|{client_secret}|{app_version}|{service}|CRACK-TRAP"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def verify_trap_signature(payload: dict, signature: str) -> bool:
    if not signature:
        return False
    secret = get_trap_secret()
    if not secret:
        return False
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hmac.new(get_trap_secret().encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())
