"""
Aionion Capital — Token Refresh Helper
=======================================
Aionion does not expose a public OAuth flow, so the Bearer token
must be grabbed from the browser after logging in.

Usage:
  python3 aionion_auth.py

This opens https://dashboard.aionion.com in your browser and waits
for you to log in, then prompts you to paste the token from DevTools.

How to get the token from DevTools:
  1. Open https://dashboard.aionion.com in Chrome/Firefox
  2. Open DevTools → Network tab
  3. Log in (or refresh the page if already logged in)
  4. Click any API call (e.g. /api/Dashboard/GetDashboard)
  5. Copy the value of the Authorization header (starts with "Bearer eyJ...")
  6. Paste it here when prompted.

The token is saved to .env and the backend is restarted automatically.
"""
import os, sys, webbrowser, time, subprocess
from dotenv import load_dotenv, set_key

ENV_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

load_dotenv(ENV_PATH, override=True)

def main():
    print("=" * 55)
    print(" TRaMS - Aionion Capital Token Refresh")
    print("=" * 55)
    print()
    print("Opening https://dashboard.aionion.com in your browser...")
    webbrowser.open("https://dashboard.aionion.com")
    print()
    print("Steps:")
    print("  1. Log in to your Aionion Capital account")
    print("  2. Open DevTools (F12 or Cmd+Option+I)")
    print("  3. Go to Network tab")
    print("  4. Click any API call (e.g. GetDashboard)")
    print("  5. Copy the Authorization header value")
    print("     (starts with 'Bearer eyJ...')")
    print()

    raw = input("Paste the token here (with or without 'Bearer '): ").strip()
    if not raw:
        print("No token entered. Exiting.")
        sys.exit(1)

    # Strip "Bearer " prefix if present
    token = raw.replace("Bearer ", "").replace("bearer ", "").strip()

    if not token.startswith("eyJ"):
        print(f"⚠️  Warning: token doesn't look like a JWT (expected to start with 'eyJ')")
        confirm = input("Save anyway? (y/N): ").strip().lower()
        if confirm != "y":
            sys.exit(1)

    # Validate and show expiry
    try:
        import base64, json
        parts = token.split(".")
        pad   = parts[1] + "=" * (4 - len(parts[1]) % 4)
        pl    = json.loads(base64.b64decode(pad))
        exp   = pl.get("exp", 0)
        uid   = pl.get("unique_name") or pl.get("LoginId") or pl.get("sub") or "unknown"
        if exp:
            import datetime
            expiry = datetime.datetime.fromtimestamp(exp)
            print(f"✅ Token for user: {uid}")
            print(f"   Expires: {expiry.strftime('%Y-%m-%d %H:%M:%S')}")
            if exp < time.time():
                print("⚠️  This token is already expired!")
                confirm = input("Save anyway? (y/N): ").strip().lower()
                if confirm != "y":
                    sys.exit(1)
    except Exception:
        pass

    set_key(ENV_PATH, "AIONION_TOKEN", token)
    print(f"\n✅ Token saved to .env")
    # Auto-push to Render cloud
    try:
        from render_push import push_env_to_render
        push_env_to_render({"AIONION_TOKEN": token})
    except Exception as re:
        print(f"[Render] Push skipped: {re}")

    # Restart backend
    subprocess.run(["pkill", "-f", "uvicorn"], capture_output=True)
    time.sleep(1.5)
    venv_py = os.path.join(BACKEND_DIR, "venv/bin/python3")
    subprocess.Popen(
        [venv_py, "-m", "uvicorn", "main:app", "--reload",
         "--host", "0.0.0.0", "--port", "8000"],
        cwd=BACKEND_DIR
    )
    print("✅ Backend restarted on :8000")
    print("🎉 Aionion Capital connected!")

if __name__ == "__main__":
    main()
