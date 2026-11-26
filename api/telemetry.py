import json
import os
import uuid
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler


def _send(handler, status, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _supabase(method, path, payload=None, prefer=None):
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    url = base_url + "/rest/v1/" + path
    data = None if payload is None else json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "apikey": service_key,
            "Authorization": "Bearer " + service_key,
            "Content-Type": "application/json",
            "Prefer": prefer or "return=minimal",
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read()


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if (
            not os.environ.get("SUPABASE_URL")
            or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        ):
            _send(self, 503, {"error": "Backend no configurado"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length < 1 or content_length > 8192:
                raise ValueError("Tamaño de solicitud no válido")

            data = json.loads(self.rfile.read(content_length))

            installation_id = str(
                uuid.UUID(str(data.get("installation_id", "")))
            )

            version = str(data.get("launcher_version", "")).strip()[:40]
            if not version or not all(
                char.isalnum() or char in "._+-" for char in version
            ):
                raise ValueError("Versión no válida")

            # Optional for compatibility with older launcher builds.
            # If absent, do not overwrite the value already stored in Supabase.
            launch_count = None
            if "launch_count" in data:
                launch_count = int(data.get("launch_count"))
                if launch_count < 0:
                    raise ValueError("Contador no válido")
                launch_count = min(launch_count, 2_000_000_000)

        except (ValueError, TypeError, json.JSONDecodeError):
            _send(self, 400, {"error": "Datos de instalación no válidos"})
            return
        except Exception:
            _send(self, 400, {"error": "Solicitud no válida"})
            return

        country = self.headers.get("x-vercel-ip-country")
        if country and (
            len(country) != 2 or not country.isalpha()
        ):
            country = None

        consent = data.get("optional_consent") is True

        row = {
            "installation_id": installation_id,
            "launcher_version": version,
            "optional_consent": consent,
        }

        if country:
            row["country"] = country.upper()

        if launch_count is not None:
            row["launch_count"] = launch_count

        try:
            # Upsert updates the installation row instead of creating a new
            # installation for each synchronization.
            _supabase(
                "POST",
                "installations?on_conflict=installation_id",
                row,
                "resolution=merge-duplicates,return=minimal",
            )

            # Only explicitly named optional events are recorded here.
            # "installation_sync" is deliberately NOT a launch event.
            optional_event = str(data.get("optional_event", "")).strip()[:40]
            allowed_optional_events = {
                "mod_enabled",
                "mod_disabled",
                "instance_created",
                "instance_deleted",
                "game_started",
            }

            if consent and optional_event in allowed_optional_events:
                _supabase(
                    "POST",
                    "analytics_events",
                    {
                        "installation_id": installation_id,
                        "event_type": optional_event,
                        "launcher_version": version,
                    },
                    "return=minimal",
                )

            _send(
                self,
                200,
                {
                    "ok": True,
                    "installation_id": installation_id,
                    "launch_count_received": launch_count is not None,
                },
            )

        except urllib.error.HTTPError as error:
            _send(
                self,
                502,
                {
                    "error": "No se pudo guardar el registro",
                    "status": error.code,
                },
            )
        except Exception:
            _send(
                self,
                502,
                {"error": "No se pudo conectar con la base de datos"},
            )

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "POST, OPTIONS")
        self.end_headers()

    def log_message(self, *args):
        pass
