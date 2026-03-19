
import secrets
import time
import uuid
import logging
import os
import yaml

from flask import Blueprint, request, make_response, redirect, url_for, render_template

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

COOKIE_NAME = "jkriver_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year
_MAX_FAILS = 5
_LOCK_SECONDS = 600  # 10 minutes

# ip -> {"fails": int, "locked_until": float}
_rate: dict = {}

_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.yaml")


def _load_auth_config():
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    pm = raw.get("public_mode", {})
    return pm.get("enabled", False), pm.get("access_token", "")


def _save_token(token: str):
    with open(_SETTINGS_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    # Replace the access_token line
    import re
    content = re.sub(
        r"(access_token:\s*)\"[^\"]*\"",
        f'access_token: "{token}"',
        content,
    )
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        f.write(content)


def init_auth():
    """Call once at app startup. Returns (public_mode_enabled, token)."""
    enabled, token = _load_auth_config()
    if not enabled:
        return False, ""
    if not token:
        token = str(uuid.uuid4())
        _save_token(token)
        print("\n" + "=" * 60)
        print("  PUBLIC MODE: access token auto-generated")
        print(f"  TOKEN: {token}")
        print("  Share this token with authorized users.")
        print("=" * 60 + "\n")
    else:
        print(f"\n[Auth] Public mode enabled. Token: {token}\n")
    return True, token


# Module-level state (set by init_auth)
_public_mode = False
_access_token = ""


def setup(app):
    enabled, token = init_auth()
    global _public_mode, _access_token
    _public_mode = enabled
    _access_token = token

    @app.before_request
    def check_auth():
        if not _public_mode:
            return None
        # Always allow the unlock routes
        if request.endpoint in ("auth.unlock_get", "auth.unlock_post"):
            return None

        ip = request.remote_addr or "unknown"
        entry = _rate.get(ip, {"fails": 0, "locked_until": 0.0})
        if entry["locked_until"] > time.time():
            return make_response("Too many failed attempts. Try again later.", 429)

        token = request.cookies.get(COOKIE_NAME, "")
        if _token_valid(token):
            return None

        return redirect(url_for("auth.unlock_get"))


def _token_valid(token: str) -> bool:
    if not _access_token:
        return False
    try:
        return secrets.compare_digest(token.encode(), _access_token.encode())
    except Exception:
        return False


def _record_failure(ip: str):
    entry = _rate.setdefault(ip, {"fails": 0, "locked_until": 0.0})
    entry["fails"] += 1
    if entry["fails"] >= _MAX_FAILS:
        entry["locked_until"] = time.time() + _LOCK_SECONDS
        entry["fails"] = 0
        logger.warning("Auth: IP %s locked for %ds after repeated failures", ip, _LOCK_SECONDS)


def _record_success(ip: str):
    _rate.pop(ip, None)


@auth_bp.route("/unlock", methods=["GET"])
def unlock_get():
    return render_template("unlock.html")


@auth_bp.route("/unlock", methods=["POST"])
def unlock_post():
    ip = request.remote_addr or "unknown"

    entry = _rate.get(ip, {"fails": 0, "locked_until": 0.0})
    if entry["locked_until"] > time.time():
        return render_template("unlock.html", error="Too many failed attempts. Try again later.")

    token = request.form.get("token", "").strip()
    if _token_valid(token):
        _record_success(ip)
        resp = make_response(redirect(url_for("chat.chat")))
        resp.set_cookie(COOKIE_NAME, token, max_age=COOKIE_MAX_AGE, httponly=False, samesite="Lax")
        return resp
    else:
        _record_failure(ip)
        return render_template("unlock.html", error="Invalid token. Please try again.")
