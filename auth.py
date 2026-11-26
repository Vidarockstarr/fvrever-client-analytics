import os, json, time, hmac, hashlib, base64
from http.server import BaseHTTPRequestHandler

COOKIE = "fvrever_session"
TTL = 60 * 60 * 12

def _secret():
    return os.environ.get("SESSION_SECRET", "")

def _json(handler, status, data, headers=None):
    body=json.dumps(data, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type","application/json; charset=utf-8")
    handler.send_header("Cache-Control","no-store")
    handler.send_header("Content-Length",str(len(body)))
    if headers:
        for k,v in headers.items(): handler.send_header(k,v)
    handler.end_headers()
    handler.wfile.write(body)

def _token():
    payload=base64.urlsafe_b64encode(json.dumps({"exp":int(time.time())+TTL}).encode()).decode().rstrip("=")
    sig=hmac.new(_secret().encode(),payload.encode(),hashlib.sha256).hexdigest()
    return payload+"."+sig

def _valid(handler):
    if not _secret(): return False
    raw=handler.headers.get("Cookie","")
    cookies={}
    for item in raw.split(";"):
        if "=" in item:
            k,v=item.strip().split("=",1); cookies[k]=v
    token=cookies.get(COOKIE,"")
    try:
        payload,sig=token.rsplit(".",1)
        expected=hmac.new(_secret().encode(),payload.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): return False
        data=json.loads(base64.urlsafe_b64decode(payload+"="*((4-len(payload)%4)%4)))
        return int(data.get("exp",0)) > int(time.time())
    except Exception:
        return False

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if _valid(self): _json(self,200,{"authenticated":True})
        else: _json(self,401,{"error":"No autorizado"})

    def do_POST(self):
        try:
            length=min(int(self.headers.get("Content-Length","0")),4096)
            data=json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            _json(self,400,{"error":"Solicitud no válida"}); return
        password=os.environ.get("DASHBOARD_PASSWORD","")
        if not password or not _secret():
            _json(self,503,{"error":"Falta configurar DASHBOARD_PASSWORD y SESSION_SECRET en Vercel"}); return
        supplied=str(data.get("password",""))
        if not hmac.compare_digest(supplied.encode(),password.encode()):
            _json(self,401,{"error":"Contraseña incorrecta"}); return
        cookie=f"{COOKIE}={_token()}; Path=/; Max-Age={TTL}; HttpOnly; Secure; SameSite=Strict"
        _json(self,200,{"authenticated":True},{"Set-Cookie":cookie})

    def do_DELETE(self):
        cookie=f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"
        _json(self,200,{"authenticated":False},{"Set-Cookie":cookie})

    def log_message(self,*args): pass
