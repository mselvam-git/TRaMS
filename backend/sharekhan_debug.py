import os, sys, webbrowser, threading, urllib.parse, base64, requests, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from base64 import urlsafe_b64encode, urlsafe_b64decode
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from Crypto.Cipher import AES
from dotenv import load_dotenv, set_key

ENV_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(ENV_PATH, override=True)

API_KEY    = os.getenv("SHAREKHAN_API_KEY",    "").strip()
SECRET_KEY = os.getenv("SHAREKHAN_SECRET_KEY", "").strip()
_key       = SECRET_KEY.encode("utf-8")
_iv        = base64.b64decode("AAAAAAAAAAAAAAAAAAAAAA==")
_state     = {"raw_token": None, "done": threading.Event()}

def b64url_dec(s):
    if isinstance(s, str): s = s.encode()
    s += b"=" * (4 - len(s) % 4)
    return urlsafe_b64decode(s)

def b64url_enc(data):
    return urlsafe_b64encode(data).rstrip(b"=").decode()

def decrypt_token(tok):
    enc    = b64url_dec(tok)
    cipher = AES.new(_key, AES.MODE_GCM, nonce=b"\x00" * 16)
    return cipher.decrypt_and_verify(enc[:-16], enc[-16:]).decode()

def encrypt_gcm(plaintext):
    raw = plaintext.encode("utf-8")
    enc = Cipher(algorithms.AES(_key), modes.GCM(_iv, None, 16), default_backend()).encryptor()
    ct  = enc.update(raw) + enc.finalize()
    return b64url_enc(ct + enc.tag)

def try_post(label, api_key, enc_str, extra_body=None):
    url  = "https://api.sharekhan.com/skapi/services/access/token"
    hdrs = {"api-key": api_key, "access-token": "", "Content-type": "application/json"}
    body = {"apiKey": api_key, "requestToken": enc_str, "state": "12345"}
    if extra_body:
        body.update(extra_body)
    r = requests.post(url, data=json.dumps(body), headers=hdrs, timeout=15)
    ok = r.status_code == 200
    print(f"  [{label}] {'OK' if ok else r.status_code}: {r.text[:100]}")
    return r.json() if ok else None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        raw_query = self.path.split("?", 1)[1] if "?" in self.path else ""
        raw_token = None
        for part in raw_query.split("&"):
            if part.lower().startswith("request_token="):
                raw_token = part.split("=", 1)[1]
                break
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if raw_token:
            _state["raw_token"] = raw_token
            self.wfile.write(b"<html><body style='background:#0B0D1A;color:#00C7B1;text-align:center;padding:60px;font-family:sans-serif'><h1>Token Captured - Close Tab</h1></body></html>")
            _state["done"].set()
        else:
            self.wfile.write(f"<pre>No token: {raw_query}</pre>".encode())
    def log_message(self, *a): pass

try:
    server = HTTPServer(("", 80), Handler)
    print("Port 80 ready")
except PermissionError:
    print("Need sudo"); sys.exit(1)

threading.Thread(target=server.serve_forever, daemon=True).start()
login_url = f"https://api.sharekhan.com/skapi/auth/login.html?api_key={API_KEY}&state=12345"
print(f"Opening: {login_url}")
webbrowser.open(login_url)
print("Waiting...")
_state["done"].wait(timeout=180)
server.shutdown()

raw_token = _state.get("raw_token")
if not raw_token:
    print("No token"); sys.exit(1)

print(f"\nRAW (no decode): [{raw_token}]  len={len(raw_token)}")
v1 = urllib.parse.unquote(raw_token)
v2 = urllib.parse.unquote_plus(raw_token)
print(f"unquote:         [{v1}]")
print(f"unquote_plus:    [{v2}]")

results = {}
for vname, tok in [("unquote", v1), ("unquote_plus", v2), ("raw", raw_token)]:
    try:
        dec = decrypt_token(tok)
        print(f"\n{vname} decrypts -> [{dec}]")
        parts = dec.split("|")
        if len(parts) == 2:
            swap   = parts[1] + "|" + parts[0]
            noswap = dec
            for lbl, enc in [("swap", encrypt_gcm(swap)), ("noswap", encrypt_gcm(noswap)),
                              ("raw_tok", tok), ("decrypted", dec)]:
                r = try_post(f"{vname}/{lbl}", API_KEY, enc)
                if r:
                    results["winner"] = r
                    break
        if "winner" in results:
            break
    except Exception as e:
        print(f"  {vname} fail: {e}")

print("\n-- SDK --")
try:
    from SharekhanApi.sharekhanConnect import SharekhanConnect
    sk  = SharekhanConnect(api_key=API_KEY, privateKey=API_KEY)
    enc = sk.generate_session(v1, SECRET_KEY)
    print(f"  encStr: {enc[:50]}")
    r   = try_post("SDK", API_KEY, enc)
    if r:
        results["winner"] = r
except Exception as e:
    print(f"  SDK err: {e}")

print("\n" + "="*60)
if "winner" in results:
    resp = results["winner"]
    print("SUCCESS!")
    tok  = (resp.get("accessToken") or resp.get("access_token") or
            resp.get("token") or resp.get("sessionToken") or resp.get("jwtToken"))
    if tok:
        set_key(ENV_PATH, "SHAREKHAN_ACCESS_TOKEN", str(tok))
        print(f"Saved token: {str(tok)[:60]}")
        import subprocess, time
        subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
        time.sleep(1)
        venv_py = os.path.join(BACKEND_DIR, "venv/bin/python3")
        subprocess.Popen([venv_py, "-m", "uvicorn", "main:app", "--reload",
                          "--host", "0.0.0.0", "--port", "8000"], cwd=BACKEND_DIR)
        print("Backend restarted on :8000")
else:
    print("ALL failed. Raw token saved to .env for analysis.")
    set_key(ENV_PATH, "SHAREKHAN_REQUEST_TOKEN_RAW", raw_token)
    print(f"Raw: {raw_token}")
