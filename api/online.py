"""FVREVER launcher online-presence endpoint.

POST /api/online
{
    "action": "heartbeat" | "offline",
    "installation_id": "<persistent installation UUID>",
    "launcher_version": "1.2.0"
}

This endpoint is intentionally independent from the dashboard's browser-cookie
login: the launcher does not have a dashboard session. The installation UUID
is an identifier, not an authentication secret; see deployment notes.
"""
from __future__ import annotations

import json
import os
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler


MAX_BODY = 2048
TABLE = "online_sessions"


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _supabase_request(method: str, query: str, payload: dict) -> None:
    base_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base_url or not service_key:
        raise RuntimeError("Supabase environment is not configured")

    url = f"{base_url}/rest/v1/{TABLE}{query}"
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        response.read()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            raw_length = self.headers.get("Content-Length", "0")
            length = int(raw_length)
            if length <= 0 or length > MAX_BODY:
                _send_json(self, 400, {"error": "Solicitud no válida"})
                return
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError("JSON object required")
        except (ValueError, TypeError, json.JSONDecodeError):
            _send_json(self, 400, {"error": "JSON no válido"})
            return

        action = str(data.get("action", "heartbeat")).strip().lower()
        raw_id = str(data.get("installation_id", "")).strip()
        version = str(data.get("launcher_version", "")).strip()

        if action not in {"heartbeat", "offline"}:
            _send_json(self, 400, {"error": "Acción no válida"})
            return

        try:
            installation_id = str(uuid.UUID(raw_id))
        except (ValueError, AttributeError, TypeError):
            _send_json(self, 400, {"error": "installation_id no válido"})
            return

        if not version or len(version) > 40:
            _send_json(self, 400, {"error": "launcher_version no válida"})
            return

        now = datetime.now(timezone.utc).isoformat()
        row = {
            "installation_id": installation_id,
            "launcher_version": version,
            "last_heartbeat": now,
            "is_online": action == "heartbeat",
        }

        try:
            if action == "heartbeat":
                # Upsert keeps one row per installation, never one row per ping.
                _supabase_request(
                    "POST",
                    "?on_conflict=installation_id",
                    row,
                )
            else:
                # Do not create a new row just because an offline notice arrived.
                _supabase_request(
                    "PATCH",
                    f"?installation_id=eq.{installation_id}",
                    {"is_online": False, "last_heartbeat": now},
                )
            _send_json(self, 200, {"ok": True, "online": action == "heartbeat"})
        except urllib.error.HTTPError as error:
            # Avoid returning Supabase response bodies or credentials to clients.
            _send_json(self, 502, {"error": "Error guardando presencia", "status": error.code})
        except Exception:
            _send_json(self, 502, {"error": "No se pudo actualizar la presencia"})

    def do_GET(self):
        _send_json(self, 405, {"error": "Método no permitido"})

    def log_message(self, *args):
        pass
