import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone, timedelta
from api.auth import _valid


ONLINE_TIMEOUT_SECONDS = 60


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
            online_data, _ = _supabase(
                "online_sessions?select=installation_id,launcher_version,"
                "last_heartbeat,is_online&order=last_heartbeat.desc&limit=5000"
            )

            rows = json.loads(installations_data or b"[]")
            events = json.loads(events_data or b"[]")
            state = json.loads(state_data or b"[]")
            online_rows = json.loads(online_data or b"[]")
            reset_at = state[0].get("stats_reset_at") if state else None

            # A heartbeat arrives every 15 seconds. A 60-second window
            # tolerates temporary network delays and detects crashed clients.
            now_utc = datetime.now(timezone.utc)
            online_sessions = []
            online_versions = {}
            online_now = 0

            for session in online_rows:
                last_heartbeat = session.get("last_heartbeat") or ""
                try:
                    heartbeat_at = datetime.fromisoformat(
                        last_heartbeat.replace("Z", "+00:00")
                    )
                    if heartbeat_at.tzinfo is None:
                        heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
                    age = now_utc - heartbeat_at
                    fresh = timedelta(0) <= age <= timedelta(
                        seconds=ONLINE_TIMEOUT_SECONDS
                    )
                except (TypeError, ValueError):
                    fresh = False

                is_online = bool(session.get("is_online")) and fresh
                if is_online:
                    online_now += 1
                    version = session.get("launcher_version") or "Desconocida"
                    online_versions[version] = online_versions.get(version, 0) + 1

                online_sessions.append({
                    "installation_id": session.get("installation_id"),
                    "launcher_version": session.get("launcher_version"),
                    "last_heartbeat": last_heartbeat,
                    "is_online": is_online,
                })

            versions, countries = {}, {}
            for row in rows:
                version = row.get("launcher_version") or "Desconocida"
                versions[version] = versions.get(version, 0) + 1
                country = row.get("country") or "Desconocido"
                countries[country] = countries.get(country, 0) + 1

            # Preserve each launcher's lifetime counter, but display only
            # launches accumulated after the latest dashboard reset.
            total_launches = sum(
                max(
                    0,
                    int(row.get("launch_count") or 0)
                    - int(row.get("launch_count_baseline") or 0),
                )
                for row in rows
            )

            today = datetime.now(timezone.utc).date().isoformat()
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
                "online_now": online_now,
                "online_versions": online_versions,
                "online_sessions": online_sessions,
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
