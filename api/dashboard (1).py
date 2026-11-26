import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone
from api.auth import _valid


def _supabase(path, prefer="count=exact"):
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    request = urllib.request.Request(
        url,
        headers={
            "apikey": key,
            "Authorization": "Bearer " + key,
            "Prefer": prefer,
        },
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read(), dict(response.headers)


def _json(handler, status, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _valid(self):
            _json(self, 401, {"error": "No autorizado"})
            return

        try:
            installations_data, installations_headers = _supabase(
                "installations"
                "?select=installation_id,launcher_version,country,"
                "first_seen,last_seen,optional_consent,launch_count,"
                "launch_count_baseline"
                "&order=last_seen.desc.nullslast&limit=5000"
            )
            events_data, _ = _supabase(
                "analytics_events?select=id,installation_id,event_type,"
                "launcher_version,created_at&order=created_at.desc&limit=5000"
            )
            state_data, _ = _supabase(
                "dashboard_stats_state?select=stats_reset_at&id=eq.true&limit=1"
            )

            rows = json.loads(installations_data or b"[]")
            events = json.loads(events_data or b"[]")
            state = json.loads(state_data or b"[]")
            reset_at = state[0].get("stats_reset_at") if state else None

            versions, countries = {}, {}
            for row in rows:
                version = row.get("launcher_version") or "Desconocida"
                versions[version] = versions.get(version, 0) + 1
                country = row.get("country") or "Desconocido"
                countries[country] = countries.get(country, 0) + 1

            # Keep the launcher's lifetime counter intact on each client.
            # The dashboard displays only launches after the server-side baseline.
            total_launches = sum(
                max(
                    0,
                    int(row.get("launch_count") or 0)
                    - int(row.get("launch_count_baseline") or 0),
                )
                for row in rows
            )

            now = datetime.now(timezone.utc)
            today = now.date().isoformat()
            active_today = 0
            for row in rows:
                last_seen = row.get("last_seen") or ""
                if not last_seen.startswith(today):
                    continue
                if reset_at and last_seen < reset_at:
                    continue
                active_today += 1

            content_range = installations_headers.get("Content-Range", "")
            total_installations = content_range.split("/")[-1]
            if total_installations in ("", "*"):
                total_installations = str(len(rows))

            _json(self, 200, {
                "total_installations": total_installations,
                "active_today": active_today,
                "total_launches": total_launches,
                "installations": rows,
                "versions": versions,
                "countries": countries,
                "events": events,
                "stats_reset_at": reset_at,
            })

        except urllib.error.HTTPError as error:
            _json(self, 502, {
                "error": "Error consultando Supabase",
                "status": error.code,
            })
        except Exception:
            _json(self, 502, {"error": "No se pudieron cargar las estadísticas"})

    def log_message(self, *args):
        pass
