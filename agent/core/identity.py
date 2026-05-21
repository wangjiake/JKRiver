"""Resolve an access token to an owner (account) id.

Family / multi-account mode. Each request carries a token (cookie for the
Flask app, X-Device-Token header for the FastAPI app, channel external_id
for Telegram/Discord). This module turns that token into an integer
owner_id that storage queries filter by.

Tokens are stored hashed (SHA-256). The plaintext only ever lives in the
client cookie / invite URL — never in the DB. The verification path hashes
the inbound token and looks it up by `token_hash`.

Backwards-compatible: if a token matches the legacy
`public_mode.access_token` in settings.yaml, it resolves to owner_id=1.
"""

import hashlib
import time
import threading

from psycopg2.extras import RealDictCursor

from agent.storage._db import get_db_connection
from agent.config import load_config

_CACHE_TTL = 60.0  # seconds
_cache_lock = threading.Lock()
_cache: dict[str, tuple[int, float]] = {}  # plaintext token -> (owner_id, expires_at)

# IM identity cache — channel_identities is on the IM message hot path, so we
# cache lookups for the same TTL. Family-router channel create/delete calls
# invalidate_channel_cache() so UI changes take effect immediately.
_channel_cache_lock = threading.Lock()
_channel_cache: dict[tuple[str, str], tuple[int | None, float]] = {}

DEFAULT_OWNER_ID = 1
ADMIN_OWNER_ID = 1  # Owner that can manage family accounts, tokens, channels, and system config.


def is_admin(owner_id: int | None) -> bool:
    """The default 'jk' account (owner_id=1) is the family admin."""
    return owner_id == ADMIN_OWNER_ID


def hash_token(token: str) -> str:
    """SHA-256 hex digest of a plaintext token (DB key)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_prefix(token: str, n: int = 8) -> str:
    """First n chars of a plaintext token — safe to show in UI as preview."""
    return token[:n]


def _public_mode_token() -> str:
    cfg = load_config()
    pm = cfg.get("public_mode", {}) or {}
    if not pm.get("enabled", False):
        return ""
    return str(pm.get("access_token", "") or "")


def _public_mode_enabled() -> bool:
    cfg = load_config()
    return bool((cfg.get("public_mode", {}) or {}).get("enabled", False))


def detect_device_type(user_agent: str | None) -> str:
    """Cheap heuristic from User-Agent. Returns 'mobile' / 'tablet' / 'desktop' / 'bot' / 'unknown'."""
    if not user_agent:
        return "unknown"
    ua = user_agent.lower()
    if any(b in ua for b in ("bot", "crawler", "spider", "curl/", "wget/", "python-", "httpx/")):
        return "bot"
    if "ipad" in ua or ("tablet" in ua and "mobile" not in ua):
        return "tablet"
    if any(m in ua for m in ("iphone", "android", "mobile", "ipod")):
        return "mobile"
    return "desktop"


def detect_device_name(user_agent: str | None) -> str:
    """Pretty-name guess for a UA — what shows in the device list by default."""
    if not user_agent:
        return "Unknown device"
    ua = user_agent
    ua_low = ua.lower()
    # Browser
    if "edg/" in ua_low:
        browser = "Edge"
    elif "chrome/" in ua_low and "safari/" in ua_low:
        browser = "Chrome"
    elif "firefox/" in ua_low:
        browser = "Firefox"
    elif "safari/" in ua_low:
        browser = "Safari"
    elif "curl/" in ua_low:
        browser = "curl"
    elif "python" in ua_low or "httpx" in ua_low:
        browser = "Script"
    else:
        browser = "Browser"
    # OS / platform
    if "iphone" in ua_low:
        plat = "iPhone"
    elif "ipad" in ua_low:
        plat = "iPad"
    elif "android" in ua_low:
        plat = "Android"
    elif "mac os x" in ua_low or "macintosh" in ua_low:
        plat = "Mac"
    elif "windows" in ua_low:
        plat = "Windows"
    elif "linux" in ua_low:
        plat = "Linux"
    else:
        plat = ""
    return f"{browser} on {plat}".strip() if plat else browser


def resolve_owner_id(token: str | None, *,
                     user_agent: str | None = None,
                     ip: str | None = None) -> int | None:
    """Return owner_id for the given token, or None if invalid.

    When user_agent / ip are provided, the matching row's last_used_at /
    last_ua / last_ip / device_type / device_name (if blank) are updated
    asynchronously so the device list reflects current activity.

    Resolution order:
      1) lookup access_tokens by SHA-256(token) (multi-owner mode)
      2) match settings.yaml public_mode.access_token (legacy single-user)
      3) if public_mode is disabled altogether, fall back to DEFAULT_OWNER_ID
    """
    if not token:
        if not _public_mode_token() and not _public_mode_enabled():
            return DEFAULT_OWNER_ID
        return None

    now = time.time()
    with _cache_lock:
        hit = _cache.get(token)
        if hit and hit[1] > now:
            owner_id = hit[0]
            # touch async even on cache hit — but rate-limit to once / minute via cache TTL.
            _touch_last_used(token, user_agent=user_agent, ip=ip)
            return owner_id

    h = hash_token(token)
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Refuse revoked tokens AND pending-admin-approval tokens. A
            # pending token has a cookie already set client-side but the
            # admin must approve the device first; until then it cannot auth.
            cur.execute(
                "SELECT owner_id FROM access_tokens "
                "WHERE token_hash = %s AND revoked_at IS NULL "
                "AND (pending_approval IS NULL OR pending_approval = FALSE)",
                (h,),
            )
            row = cur.fetchone()
    except Exception:
        row = None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if row:
        owner_id = int(row["owner_id"])
        with _cache_lock:
            _cache[token] = (owner_id, now + _CACHE_TTL)
        _touch_last_used(token, user_agent=user_agent, ip=ip)
        return owner_id

    legacy = _public_mode_token()
    if legacy and token == legacy:
        with _cache_lock:
            _cache[token] = (DEFAULT_OWNER_ID, now + _CACHE_TTL)
        return DEFAULT_OWNER_ID

    return None


def _touch_last_used(token: str, *, user_agent: str | None = None, ip: str | None = None) -> None:
    """Update last_used_at + last_ua + last_ip on the row for this token.

    If device_type / device_name are still NULL (first hit after invite),
    auto-fill them from the user agent. Also kicks off an async geoip
    lookup that, on success, updates last_country / last_city and (if the
    city changed) appends a `new_location` row to access_log.
    """
    try:
        h = hash_token(token)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                if user_agent:
                    cur.execute(
                        "UPDATE access_tokens "
                        "SET last_used_at = NOW(), "
                        "    last_ua  = %s, "
                        "    last_ip  = COALESCE(%s, last_ip), "
                        "    device_type = COALESCE(NULLIF(device_type, ''), %s), "
                        "    device_name = COALESCE(NULLIF(device_name, ''), %s) "
                        "WHERE token_hash = %s "
                        "RETURNING id, owner_id, last_city",
                        (user_agent, ip, detect_device_type(user_agent),
                         detect_device_name(user_agent), h),
                    )
                else:
                    cur.execute(
                        "UPDATE access_tokens SET last_used_at = NOW() WHERE token_hash = %s "
                        "RETURNING id, owner_id, last_city",
                        (h,),
                    )
                touched = cur.fetchone()
            conn.commit()
        finally:
            conn.close()

        if touched and ip:
            _kickoff_geoip(token_id=touched[0], owner_id=touched[1],
                           prior_city=touched[2], ip=ip)
    except Exception:
        pass  # best-effort


def _kickoff_geoip(*, token_id: int, owner_id: int, prior_city: str | None, ip: str) -> None:
    """Async geo lookup; on success update access_tokens.last_country/city
    and write access_log if city changed."""
    try:
        from agent.services.geoip import lookup_async
    except Exception:
        return

    def _on_info(info: dict):
        if not info:
            return
        country = info.get("country")
        city = info.get("city")
        if not city and not country:
            return
        try:
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE access_tokens SET last_country = %s, last_city = %s "
                        "WHERE id = %s",
                        (country, city, token_id),
                    )
                conn.commit()
            finally:
                conn.close()
            # If city changed, write an access_log row.
            if city and city != prior_city:
                try:
                    from agent.services.geoip import record_access_event
                    event = "new_device" if not prior_city else "new_location"
                    record_access_event(owner_id, token_id, event, ip, info,
                                        details={"prior_city": prior_city})
                except Exception:
                    pass
        except Exception:
            pass

    lookup_async(ip, callback=_on_info)


def get_account(owner_id: int) -> dict | None:
    """Return {id, name, display_name} for an owner, or None if missing."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, display_name FROM accounts WHERE id = %s",
                (owner_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_account_name(owner_id: int) -> str | None:
    acc = get_account(owner_id)
    if not acc:
        return None
    return acc.get("display_name") or acc.get("name")


def resolve_channel_owner(channel: str, external_id: str) -> int | None:
    """Look up the owner for a Telegram/Discord/Withings external user id.

    Cached for _CACHE_TTL seconds so an active IM session doesn't hit Postgres
    on every message. The family router invalidates on create/delete.
    """
    key = (channel, str(external_id))
    now = time.time()
    with _channel_cache_lock:
        hit = _channel_cache.get(key)
        if hit and hit[1] > now:
            return hit[0]

    owner_id: int | None = None
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT owner_id FROM channel_identities "
                "WHERE channel = %s AND external_id = %s",
                (channel, str(external_id)),
            )
            row = cur.fetchone()
            owner_id = int(row[0]) if row else None
    except Exception:
        owner_id = None
    finally:
        try:
            conn.close()
        except Exception:
            pass

    with _channel_cache_lock:
        _channel_cache[key] = (owner_id, now + _CACHE_TTL)
    return owner_id


def invalidate_cache(token: str | None = None) -> None:
    with _cache_lock:
        if token:
            _cache.pop(token, None)
        else:
            _cache.clear()


def invalidate_channel_cache(channel: str | None = None,
                             external_id: str | None = None) -> None:
    """Drop cached channel_identities entries. Call after create/delete in the
    family router so UI changes take effect on the next IM message."""
    with _channel_cache_lock:
        if channel and external_id:
            _channel_cache.pop((channel, str(external_id)), None)
        else:
            _channel_cache.clear()


def current_token_id(token: str | None) -> int | None:
    """Return the access_tokens.id for the given token, or None.

    Used by the UI to mark the 'current device' in the family list (so we
    can disable the Sign-out button for the request's own session).
    """
    if not token:
        return None
    try:
        h = hash_token(token)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM access_tokens WHERE token_hash = %s AND revoked_at IS NULL",
                    (h,),
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
        finally:
            conn.close()
    except Exception:
        return None
