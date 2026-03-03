"""
Zerodha Auto Token Generator
─────────────────────────────
Run this script once each morning before starting the dashboard.

What it does:
  1. Opens Kite login page in your browser
  2. You log in + complete 2FA on Kite's website
  3. Kite redirects back to this script (local server on port 5001)
  4. Script extracts request_token, generates access_token
  5. Saves ZERODHA_ACCESS_TOKEN to your .env file automatically

Usage:
  python3 zerodha_auth.py

Requirements:
  pip3 install kiteconnect python-dotenv
"""

import os
import sys
import webbrowser
import threading
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv, set_key

# ── Load existing .env ────────────────────────────────────────────
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(ENV_PATH)

API_KEY    = os.getenv("ZERODHA_API_KEY", "")
API_SECRET = os.getenv("ZERODHA_API_SECRET", "")
REDIRECT_PORT = 5001
REDIRECT_URL  = f"http://127.0.0.1:{REDIRECT_PORT}/callback"

# ── Validate config ───────────────────────────────────────────────
if not API_KEY or not API_SECRET:
    print("\n❌  ZERODHA_API_KEY and ZERODHA_API_SECRET not set in .env")
    print("    Add them first:\n")
    print("    ZERODHA_API_KEY=your_api_key")
    print("    ZERODHA_API_SECRET=your_api_secret\n")
    sys.exit(1)

# ── Shared state for the callback ────────────────────────────────
_received = {"request_token": None, "done": threading.Event()}


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect from Kite."""

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "request_token" in params:
            _received["request_token"] = params["request_token"][0]
            self._send_html("""
                <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#0D0F1A;color:#E8EAF0">
                <h2 style="color:#00C7B1">✅ Login successful!</h2>
                <p>Access token generated and saved to <code>.env</code>.</p>
                <p>You can close this tab and return to the dashboard.</p>
                </body></html>
            """)
            _received["done"].set()
        elif "error" in params:
            error = params.get("error_description", ["Unknown error"])[0]
            self._send_html(f"""
                <html><body style="font-family:sans-serif;text-align:center;padding:60px;background:#0D0F1A;color:#E8EAF0">
                <h2 style="color:#FF6B6B">❌ Login failed</h2>
                <p>{error}</p>
                </body></html>
            """)
            _received["done"].set()
        else:
            self._send_html("<html><body>Waiting for Kite login...</body></html>")

    def _send_html(self, html: str):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        pass  # Suppress default server logs


def generate_access_token(request_token: str) -> str:
    """Exchange request_token for access_token using Kite SDK."""
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        print("\n❌  kiteconnect not installed. Run:")
        print("    pip3 install kiteconnect\n")
        sys.exit(1)

    kite = KiteConnect(api_key=API_KEY)
    data = kite.generate_session(request_token, api_secret=API_SECRET)
    return data["access_token"]


def save_token_to_env(access_token: str):
    """Write/update ZERODHA_ACCESS_TOKEN in the .env file."""
    if not os.path.exists(ENV_PATH):
        open(ENV_PATH, "w").close()
    set_key(ENV_PATH, "ZERODHA_ACCESS_TOKEN", access_token)
    print(f"\n✅  Saved ZERODHA_ACCESS_TOKEN to {ENV_PATH}")


def open_login_url():
    """Build Kite login URL and open in browser."""
    from kiteconnect import KiteConnect
    kite = KiteConnect(api_key=API_KEY)
    login_url = kite.login_url()
    print(f"\n🌐  Opening Kite login in your browser...")
    print(f"    URL: {login_url}\n")
    print("    → Log in with your Zerodha credentials")
    print("    → Complete TOTP / 2FA")
    print("    → You'll be redirected back automatically\n")
    webbrowser.open(login_url)


def run():
    print("=" * 55)
    print("  🔑  Zerodha Auto Token Generator")
    print("=" * 55)

    # Check kiteconnect is installed
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        print("\n❌  kiteconnect not installed. Run:")
        print("    pip3 install kiteconnect python-dotenv\n")
        sys.exit(1)

    # Start local callback server
    server = HTTPServer(("127.0.0.1", REDIRECT_PORT), CallbackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"✅  Callback server listening on {REDIRECT_URL}")

    # Open browser for login
    open_login_url()

    # Wait for callback (timeout after 5 minutes)
    print("⏳  Waiting for you to complete login in the browser...")
    completed = _received["done"].wait(timeout=300)

    server.shutdown()

    if not completed:
        print("\n⏰  Timed out waiting for login. Please try again.")
        sys.exit(1)

    request_token = _received["request_token"]
    if not request_token:
        print("\n❌  Login failed or was cancelled.")
        sys.exit(1)

    print(f"\n🔄  Exchanging request_token for access_token...")
    try:
        access_token = generate_access_token(request_token)
        save_token_to_env(access_token)
        print("\n🎉  Done! Restart your dashboard backend to use the new token.")
        # Auto-push to Render cloud
        try:
            from render_push import push_env_to_render
            push_env_to_render({"ZERODHA_ACCESS_TOKEN": access_token})
        except Exception as re:
            print(f"[Render] Push skipped: {re}")
        print(f"\n    cd backend && python3 -m uvicorn main:app --reload\n")
    except Exception as e:
        print(f"\n❌  Failed to generate access token: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run()
