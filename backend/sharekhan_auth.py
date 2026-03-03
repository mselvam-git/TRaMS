"""
Sharekhan Auth - FAST version
No debug loops. Captures token, immediately POSTs with standard base64.
Run: sudo python3 sharekhan_auth.py
"""
import os, sys, webbrowser, threading, subprocess, time
import base64, requests, json
from http.server import HTTPServer, BaseHTTPRequestHandler
from base64 import b64decode, b64encode
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from Crypto.Cipher import AES
from dotenv import load_dotenv, set_key

ENV_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(ENV_PATH, override=True)

API_KEY    = os.getenv("SHAREKHAN_API_KEY",    "").strip()
SECRET_KEY = os.getenv("SHAREKHAN_SECRET_KEY", "").strip()
_key = SECRET_KEY.encode("utf-8")
_iv  = base64.b64decode("AAAAAAAAAAAAAAAAAAAAAA==")

_state = {"raw_token": None, "done": threading.Event()}

# ── Crypto ────────────────────────────────────────────────────────
def decrypt_token(raw_b64: str) -> str:
    """Decrypt standard-base64 token from Sharekhan."""
    enc    = b64decode(raw_b64)               # standard b64 (has + and =)
    cipher = AES.new(_key, AES.MODE_GCM, nonce=b"\x00" * 16)
    return cipher.decrypt_and_verify(enc[:-16], enc[-16:]).decode()

def encrypt_token(plaintext: str) -> str:
    """Re-encrypt with standard base64 output (NOT urlsafe)."""
    raw = plaintext.encode("utf-8")
    enc = Cipher(algorithms.AES(_key), modes.GCM(_iv, None, 16),
                 default_backend()).encryptor()
    ct  = enc.update(raw) + enc.finalize()
    return b64encode(ct + enc.tag).decode()   # standard b64 — key difference

# ── HTTP server ───────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = self.path.split("?", 1)[1] if "?" in self.path else ""

        # Extract token — no urllib decoding, take raw value as-is
        raw_token = None
        for part in query.split("&"):
            if part.lower().startswith("request_token="):
                raw_token = part.split("=", 1)[1]   # raw — keep + signs
                break

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if raw_token:
            _state["raw_token"] = raw_token
            self.wfile.write(b"""<html><body style="background:#0B0D1A;color:#00C7B1;
                font-family:sans-serif;text-align:center;padding:80px">
                <h1>&#10003; Login Captured</h1>
                <p>Close this tab. TRaMS is connecting...</p>
                </body></html>""")
            _state["done"].set()
        else:
            self.wfile.write(f"<pre>No token in: {query}</pre>".encode())

    def log_message(self, *a): pass

# ── Main ──────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print(" TRaMS - Sharekhan Auth")
    print("=" * 55)

    try:
        server = HTTPServer(("", 80), Handler)
        print("Listening on port 80")
    except PermissionError:
        print("Need sudo. Run: sudo python3 sharekhan_auth.py")
        sys.exit(1)

    # Drop root privileges after binding port 80 so files stay owned by selvam
    if os.geteuid() == 0:
        import pwd
        try:
            pw = pwd.getpwnam("selvam")
            os.setgid(pw.pw_gid)
            os.setuid(pw.pw_uid)
            print("Dropped root → selvam")
        except Exception as e:
            print(f"(Could not drop root: {e})")

    threading.Thread(target=server.serve_forever, daemon=True).start()

    url = f"https://api.sharekhan.com/skapi/auth/login.html?api_key={API_KEY}&state=12345"
    print(f"Opening browser: {url[:70]}")
    webbrowser.open(url)
    print("Waiting for login redirect...")

    _state["done"].wait(timeout=180)
    server.shutdown()

    raw_token = _state.get("raw_token")
    if not raw_token:
        print("No token received."); sys.exit(1)

    print(f"Token received ({len(raw_token)} chars) — posting immediately...")

    # ── Decrypt ───────────────────────────────────────────────────
    try:
        decrypted = decrypt_token(raw_token)
    except Exception as e:
        print(f"Decrypt failed: {e}"); sys.exit(1)

    parts       = decrypted.split("|")
    customer_id = parts[1] if len(parts) == 2 else "unknown"
    msg_swap    = parts[1] + "|" + parts[0]      # customerId|code
    enc_str     = encrypt_token(msg_swap)         # standard base64

    print(f"Customer ID : {customer_id}")
    print(f"encStr      : {enc_str[:40]}...")

    # ── POST ──────────────────────────────────────────────────────
    resp = requests.post(
        "https://api.sharekhan.com/skapi/services/access/token",
        data=json.dumps({"apiKey": API_KEY, "requestToken": enc_str, "state": "12345"}),
        headers={"api-key": API_KEY, "access-token": "",
                 "Content-type": "application/json"},
        timeout=15
    ).json()

    print(f"Response    : {json.dumps(resp)[:200]}")

    # ── Extract token ─────────────────────────────────────────────
    data = resp.get("data", {}) or {}
    access_token = (data.get("accessToken") or data.get("token") or
                    resp.get("accessToken")  or resp.get("token") or
                    resp.get("access_token") or resp.get("sessionToken") or
                    resp.get("jwtToken"))

    if not access_token:
        print("\nNo access token in response.")
        print("Full response:", json.dumps(resp, indent=2))
        sys.exit(1)

    # ── Save & restart ────────────────────────────────────────────
    set_key(ENV_PATH, "SHAREKHAN_ACCESS_TOKEN", str(access_token))
    set_key(ENV_PATH, "SHAREKHAN_CUSTOMER_ID",  str(customer_id))
    set_key(ENV_PATH, "SHAREKHAN_REQUEST_TOKEN", raw_token)
    print(f"\nAccess token saved!")
    # Auto-push to Render cloud
    try:
        from render_push import push_env_to_render
        push_env_to_render({"SHAREKHAN_ACCESS_TOKEN": str(access_token),
                            "SHAREKHAN_CUSTOMER_ID":  str(customer_id)})
    except Exception as re:
        print(f"[Render] Push skipped: {re}")
    print(f"Token: {str(access_token)[:60]}...")

    subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
    time.sleep(1.5)
    venv_py = os.path.join(BACKEND_DIR, "venv/bin/python3")
    subprocess.Popen(
        [venv_py, "-m", "uvicorn", "main:app", "--reload",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=BACKEND_DIR
    )
    print("Backend restarted on :8000")
    print("Sharekhan connected!")

if __name__ == "__main__":
    main()
