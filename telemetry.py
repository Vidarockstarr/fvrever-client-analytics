import os, json, uuid, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler

def _send(h,status,obj):
    b=json.dumps(obj).encode()
    h.send_response(status); h.send_header("Content-Type","application/json")
    h.send_header("Cache-Control","no-store"); h.send_header("Content-Length",str(len(b)))
    h.end_headers(); h.wfile.write(b)

def _supabase(method,path,payload=None,prefer=None):
    url=os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1/"+path
    data=None if payload is None else json.dumps(payload).encode()
    req=urllib.request.Request(url,data=data,method=method,headers={
        "apikey":os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization":"Bearer "+os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Content-Type":"application/json",
        "Prefer":prefer or "return=minimal"
    })
    with urllib.request.urlopen(req,timeout=12) as r: return r.read()

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
            _send(self,503,{"error":"Backend no configurado"}); return
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<1 or n>8192: raise ValueError()
            data=json.loads(self.rfile.read(n))
            installation_id=str(uuid.UUID(str(data.get("installation_id",""))))
            version=str(data.get("launcher_version","")).strip()[:40]
            if not version or not all(c.isalnum() or c in "._+-" for c in version):
                raise ValueError()
        except Exception:
            _send(self,400,{"error":"Datos de instalación no válidos"}); return

        country=self.headers.get("x-vercel-ip-country")
        if country and len(country)>2: country=None
        consent=data.get("optional_consent") is True
        row={"installation_id":installation_id,"launcher_version":version,"optional_consent":consent}
        if country: row["country"]=country.upper()
        try:
            _supabase("POST","installations?on_conflict=installation_id",row,
                      "resolution=merge-duplicates,return=minimal")
            if consent:
                event=str(data.get("event","launcher_start"))[:40]
                if event not in ("launcher_start","launch","session_start"):
                    event="launcher_start"
                _supabase("POST","analytics_events",{
                    "installation_id":installation_id,"event_type":event,
                    "launcher_version":version
                },"return=minimal")
            _send(self,200,{"ok":True})
        except urllib.error.HTTPError as e:
            _send(self,502,{"error":"No se pudo guardar el registro","status":e.code})
        except Exception:
            _send(self,502,{"error":"No se pudo conectar con la base de datos"})
    def do_OPTIONS(self):
        self.send_response(204); self.send_header("Allow","POST, OPTIONS"); self.end_headers()
    def log_message(self,*args): pass
