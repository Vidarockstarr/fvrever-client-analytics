# -*- coding: utf-8 -*-
import json
import logging
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

from api.auth import _valid

logger = logging.getLogger(__name__)


def _json(handler, status, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _reset_in_supabase():
    base = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    request = urllib.request.Request(
        base + "/rest/v1/rpc/reset_fvrever_dashboard_stats",
        data=b"{}",
        method="POST",
        headers={
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        if not raw:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return raw.decode("utf-8", errors="replace")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not _valid(self):
            _json(self, 401, {"error": "No autorizado"})
            return

        if not os.environ.get("SUPABASE_URL") or not os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY"
        ):
            _json(self, 503, {"error": "Backend no configurado"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > 1024:
                _json(self, 400, {"error": "Solicitud no válida"})
                return

            raw_payload = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw_payload or b"{}")

            if not isinstance(payload, dict) or payload.get("confirm") is not True:
                _json(self, 400, {"error": "Debes confirmar el reinicio"})
                return

            reset_at = _reset_in_supabase()

            _json(self, 200, {
                "ok": True,
                "message": "Estadísticas reiniciadas",
                "stats_reset_at": reset_at,
                "installations_preserved": True,
            })

        except urllib.error.HTTPError as error:
            # El cuerpo de Supabase suele contener el motivo concreto
            # (por ejemplo, permisos, función no encontrada o error SQL).
            try:
                detail = error.read().decode("utf-8", errors="replace")
            except Exception:
                detail = "(no se pudo leer el cuerpo de error)"

            logger.error(
                "Supabase RPC reset_fvrever_dashboard_stats respondió HTTP %s: %s",
                error.code,
                detail[:4000],
            )
            _json(self, 502, {
                "error": "Supabase rechazó el reinicio",
                "upstream_status": error.code,
            })

        except urllib.error.URLError as error:
            logger.exception("No se pudo conectar con Supabase: %s", error)
            _json(self, 502, {"error": "No se pudo conectar con Supabase"})

        except Exception:
            logger.exception("Error inesperado en /api/reset_stats")
            _json(self, 502, {"error": "Error interno al reiniciar estadísticas"})

    def do_GET(self):
        _json(self, 405, {"error": "Método no permitido"})

    def log_message(self, *args):
        pass
