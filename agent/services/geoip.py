"""IP geolocation lookup with caching.

Strategy:
  * 7-day cache in `geoip_cache` table — same IP isn't re-queried for a week.
  * Public IPs go to ipinfo.io (free 50k/month tier, no token needed).
  * Private/loopback IPs return None (no lookup, no log).
  * Admin can disable globally via settings.yaml `geoip.enabled: false`.
  * Errors are swallowed — geolocation is best-effort, never blocking auth.
"""
import ipaddress
import json
import logging
import threading
from datetime import datetime, timedelta, timezone

import requests

from agent.config import load_config
from agent.storage._db import get_db_connection

logger = logging.getLogger(__name__)

CACHE_TTL_DAYS = 7
LOOKUP_TIMEOUT = 3.0
_lookup_lock = threading.Lock()  # prevent duplicate concurrent lookups for same IP
_inflight: set[str] = set()


def _enabled() -> bool:
    cfg = load_config().get("geoip", {}) or {}
    return cfg.get("enabled", True)


def _is_public_ip(ip: str) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_multicast or addr.is_unspecified or addr.is_reserved)


def _lookup_cached(ip: str) -> dict | None:
    """Return {'country', 'city', 'region'} if cached & fresh, else None."""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT country, city, region, fetched_at FROM geoip_cache WHERE ip = %s",
                    (ip,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                country, city, region, fetched_at = row
                if fetched_at and (datetime.now(timezone.utc) - fetched_at).days > CACHE_TTL_DAYS:
                    return None
                return {"country": country, "city": city, "region": region}
        finally:
            conn.close()
    except Exception:
        return None


def _lookup_remote(ip: str) -> dict | None:
    """Query ipinfo.io. Returns None on any failure."""
    cfg = load_config().get("geoip", {}) or {}
    token = (cfg.get("ipinfo_token") or "").strip()
    url = f"https://ipinfo.io/{ip}/json"
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(url, headers=headers, timeout=LOOKUP_TIMEOUT)
        if r.status_code != 200:
            return None
        d = r.json()
        return {
            "country": (d.get("country") or "")[:8] or None,
            "city": d.get("city") or None,
            "region": d.get("region") or None,
            "raw": d,
        }
    except Exception as e:
        logger.debug("ipinfo lookup failed for %s: %s", ip, e)
        return None


def _save_cache(ip: str, info: dict) -> None:
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO geoip_cache (ip, country, city, region, raw, fetched_at) "
                    "VALUES (%s, %s, %s, %s, %s, NOW()) "
                    "ON CONFLICT (ip) DO UPDATE SET "
                    "country = EXCLUDED.country, city = EXCLUDED.city, "
                    "region = EXCLUDED.region, raw = EXCLUDED.raw, "
                    "fetched_at = EXCLUDED.fetched_at",
                    (ip, info.get("country"), info.get("city"),
                     info.get("region"),
                     json.dumps(info.get("raw", {}), ensure_ascii=False)),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("geoip cache write failed: %s", e)


def lookup(ip: str | None) -> dict | None:
    """Synchronous IP→location lookup with cache. Returns None when geo disabled,
    IP is private, or remote lookup fails. Caller treats None as 'unknown'.
    """
    if not ip or not _enabled() or not _is_public_ip(ip):
        return None
    cached = _lookup_cached(ip)
    if cached is not None:
        return cached
    # Prevent duplicate concurrent lookups for the same IP.
    with _lookup_lock:
        if ip in _inflight:
            return None
        _inflight.add(ip)
    try:
        info = _lookup_remote(ip)
        if info:
            _save_cache(ip, info)
            return info
        return None
    finally:
        with _lookup_lock:
            _inflight.discard(ip)


def lookup_async(ip: str | None, callback=None) -> None:
    """Fire-and-forget lookup on a background thread. Calls `callback(info)` if given."""
    if not ip or not _enabled():
        return

    def _run():
        try:
            info = lookup(ip)
            if callback and info:
                callback(info)
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


def record_access_event(owner_id: int | None, token_id: int | None,
                        event: str, ip: str | None, info: dict | None,
                        details: dict | None = None) -> None:
    """Append a row to access_log. Best-effort; failures are swallowed."""
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO access_log "
                    "(owner_id, token_id, event, ip, country, city, details) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (owner_id, token_id, event, ip,
                     (info or {}).get("country"), (info or {}).get("city"),
                     json.dumps(details or {}, ensure_ascii=False)),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as e:
        logger.debug("access_log write failed: %s", e)
