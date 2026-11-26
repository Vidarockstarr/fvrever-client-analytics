import os, json, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler
from api.auth import _valid

def _supabase(path, prefer="count=exact"):
    key=os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    req=urllib.request.Request(os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1/"+path,
        headers={"apikey":key,"Authorization":"Bearer "+key,"Prefer":prefer})
    with urllib.request.urlopen(req,timeout=12) as r:
        return r.read(), dict(r.headers)

def _json(h,status,obj):
    b=json.dumps(obj,ensure_ascii=False).encode()
    h.send_response(status); h.send_header("Content-Type","application/json; charset=utf-8")
    h.send_header("Cache-Control","no-store"); h.send_header("Content-Length",str(len(b)))
    h.end_headers(); h.wfile.write(b)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _valid(self): _json(self,401,{"error":"No autorizado"}); return
        try:
            inst,ih=_supabase("installations?select=installation_id,launcher_version,country,first_seen,last_seen,optional_consent&order=last_seen.desc&limit=5000")
            events,eh=_supabase("analytics_events?select=id,installation_id,event_type,launcher_version,created_at&order=created_at.desc&limit=5000")
            rows=json.loads(inst or b"[]"); ev=json.loads(events or b"[]")
            versions={}; countries={}
            for x in rows:
                v=x.get("launcher_version") or "Desconocida"; versions[v]=versions.get(v,0)+1
                c=x.get("country") or "Desconocido"; countries[c]=countries.get(c,0)+1
            today=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat()
            active=sum(1 for x in rows if (x.get("last_seen") or "").startswith(today))
            _json(self,200,{"total_installations":ih.get("Content-Range","").split("/")[-1],
                "active_today":active,"total_launches":len(ev),"installations":rows,
                "versions":versions,"countries":countries,"events":ev})
        except urllib.error.HTTPError as e: _json(self,502,{"error":"Error consultando Supabase","status":e.code})
        except Exception: _json(self,502,{"error":"No se pudieron cargar las estadísticas"})
    def log_message(self,*args): pass
