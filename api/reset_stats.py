import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from api.auth import _valid


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
            "Prefer": "return=representation",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not _valid(self):
            _json(self, 401, {"error": "No autorizado"})
            return

        if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
            _json(self, 503, {"error": "Backend no configurado"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024:
                _json(self, 400, {"error": "Solicitud demasiado grande"})
                return
            payload = json.loads(self.rfile.read(length) or b"{}")
            if payload.get("confirm") is not True:
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
            _json(self, 502, {
                "error": "No se pudieron reiniciar las estadísticas",
                "status": error.code,
            })
        except Exception:
            _json(self, 502, {"error": "No se pudieron reiniciar las estadísticas"})

    def do_GET(self):
        _json(self, 405, {"error": "Método no permitido"})

    def log_message(self, *args):
        pass
