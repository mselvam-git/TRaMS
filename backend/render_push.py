"""
render_push.py — Auto-push updated env vars to Render.com
Called by auth scripts after saving a new token to .env.

Usage (from any auth script):
    from render_push import push_env_to_render
    push_env_to_render({"ZERODHA_ACCESS_TOKEN": new_token})
"""
import os, requests, time
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

def push_env_to_render(updates: dict) -> bool:
    """
    Update environment variables on Render and trigger a redeploy.
    updates = {"VAR_NAME": "new_value", ...}
    Returns True on success.
    """
    load_dotenv(ENV_PATH, override=True)
    api_key    = os.getenv("RENDER_API_KEY", "").strip()
    service_id = os.getenv("RENDER_SERVICE_ID", "").strip()

    if not api_key or not service_id:
        print("[Render] RENDER_API_KEY or RENDER_SERVICE_ID not set — skipping cloud push")
        print("[Render] Add them to .env to enable automatic cloud token refresh")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    # 1. Fetch current env vars from Render
    try:
        r = requests.get(
            f"https://api.render.com/v1/services/{service_id}/env-vars",
            headers=headers, timeout=15
        )
        r.raise_for_status()
        existing = {ev["envVar"]["key"]: ev["envVar"]["id"] for ev in r.json()}
    except Exception as e:
        print(f"[Render] Failed to fetch env vars: {e}")
        return False

    # 2. Build update payload
    env_vars = []
    for key, value in updates.items():
        entry = {"key": key, "value": str(value)}
        if key in existing:
            entry["id"] = existing[key]
        env_vars.append(entry)

    # 3. PUT updated env vars
    try:
        r = requests.put(
            f"https://api.render.com/v1/services/{service_id}/env-vars",
            headers=headers, json=env_vars, timeout=15
        )
        r.raise_for_status()
        print(f"[Render] ✅ Updated {list(updates.keys())} on Render")
    except Exception as e:
        print(f"[Render] Failed to update env vars: {e}")
        return False

    # 4. Trigger redeploy
    try:
        r = requests.post(
            f"https://api.render.com/v1/services/{service_id}/deploys",
            headers=headers, json={"clearCache": "do_not_clear"}, timeout=15
        )
        r.raise_for_status()
        deploy_id = r.json().get("id", "?")
        print(f"[Render] 🚀 Redeploy triggered (id: {deploy_id})")
        print(f"[Render]    Cloud backend will be live in ~60s")
        return True
    except Exception as e:
        print(f"[Render] Redeploy failed: {e}")
        return False
