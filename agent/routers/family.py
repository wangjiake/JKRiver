"""Family management endpoints — accounts, devices (tokens), invites, channels, audit.

All endpoints are admin-only (require owner_id = 1).

The token plaintext is never returned by any list/get endpoint — the admin
either looks at the device list (with prefix + UA preview) or generates a
new invite URL that contains a single-use UUID, not a token.
"""
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from agent.routers._auth import require_admin
from agent.storage import get_db_connection
from agent.core.identity import current_token_id, invalidate_cache, invalidate_channel_cache

router = APIRouter(prefix="/api/family", tags=["family"],
                   dependencies=[Depends(require_admin)])

INVITE_TTL_HOURS = 24


def _qr_svg_for(url: str) -> str | None:
    """Render an SVG QR code for the URL using `segno`.

    Returns None if segno isn't installed (UI falls back to link-only).
    Uses `currentColor` so the QR adapts to dark/light theme automatically.
    """
    try:
        import segno
    except ImportError:
        return None
    try:
        qr = segno.make(url, error='M')
        size = qr.symbol_size()[0]
        rects = []
        for y, row in enumerate(qr.matrix):
            for x, m in enumerate(row):
                if m:
                    rects.append(f'<rect x="{x}" y="{y}" width="1" height="1"/>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="-2 -2 {size + 4} {size + 4}" '
            f'fill="currentColor" shape-rendering="crispEdges">'
            f'{"".join(rects)}</svg>'
        )
    except Exception:
        return None


# ── Models ───────────────────────────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str
    display_name: str | None = None


class InviteCreate(BaseModel):
    owner_id: int
    label: str | None = None


class DeviceRename(BaseModel):
    device_name: str


class ChannelCreate(BaseModel):
    owner_id: int
    channel: str          # 'telegram' | 'discord' | 'withings'
    external_id: str


# ── audit helper ─────────────────────────────────────────────────────────────

def _audit(cur, actor, target_owner_id, action, target_type=None,
           target_id=None, details=None, ip=None):
    cur.execute(
        "INSERT INTO family_audit "
        "(actor_owner_id, target_owner_id, action, target_type, target_id, details, ip) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (actor, target_owner_id, action, target_type, target_id,
         json.dumps(details or {}, ensure_ascii=False), ip),
    )


def _actor_ip(request: Request) -> str | None:
    try:
        return request.client.host if request.client else None
    except Exception:
        return None


# ── Accounts ─────────────────────────────────────────────────────────────────

@router.get("/accounts")
async def list_accounts():
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT a.id, a.name, a.display_name, a.is_active, a.created_at, "
                "  (SELECT COUNT(*) FROM access_tokens t "
                "    WHERE t.owner_id = a.id AND t.revoked_at IS NULL) AS active_devices, "
                "  (SELECT COUNT(*) FROM channel_identities c WHERE c.owner_id = a.id) AS channels "
                "FROM accounts a ORDER BY a.id"
            )
            rows = cur.fetchall()
            return [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "display_name": r["display_name"],
                    "is_active": r["is_active"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                    "active_devices": int(r["active_devices"]),
                    "channels": int(r["channels"]),
                }
                for r in rows
            ]
    finally:
        conn.close()


@router.post("/accounts")
async def create_account(req: AccountCreate, request: Request):
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    display = (req.display_name or "").strip() or None
    actor = getattr(request.state, "owner_id", 1)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO accounts (name, display_name) VALUES (%s, %s) RETURNING id",
                    (name, display),
                )
                new_id = cur.fetchone()[0]
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=400, detail=f"create failed: {e}")
            _audit(cur, actor, new_id, "member.created", "member", new_id,
                   {"name": name, "display_name": display}, _actor_ip(request))
        conn.commit()
        return {"id": new_id, "name": name, "display_name": display}
    finally:
        conn.close()


@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, request: Request):
    if account_id == 1:
        raise HTTPException(status_code=400, detail="Cannot delete the primary admin account")
    actor = getattr(request.state, "owner_id", 1)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT name, display_name FROM accounts WHERE id = %s", (account_id,))
            ack = cur.fetchone()
            if not ack:
                raise HTTPException(status_code=404, detail="Account not found")
            name, display = ack

            # Refuse if active devices remain — admin must sign them out first.
            cur.execute(
                "SELECT COUNT(*) FROM access_tokens "
                "WHERE owner_id = %s AND revoked_at IS NULL",
                (account_id,),
            )
            if cur.fetchone()[0] > 0:
                raise HTTPException(
                    status_code=409,
                    detail="Member still has active devices. Sign them out first.",
                )

            # Refuse if there's business data.
            cur.execute(
                "SELECT "
                " (SELECT COUNT(*) FROM raw_conversations WHERE owner_id = %s) AS convs, "
                " (SELECT COUNT(*) FROM user_profile      WHERE owner_id = %s) AS profile, "
                " (SELECT COUNT(*) FROM observations      WHERE owner_id = %s) AS obs",
                (account_id, account_id, account_id),
            )
            counts = cur.fetchone()
            if counts and any(c > 0 for c in counts):
                raise HTTPException(
                    status_code=409,
                    detail=f"Member has data — {counts[0]} convs, {counts[1]} profile rows, "
                           f"{counts[2]} observations. Clear those first.",
                )
            cur.execute("DELETE FROM accounts WHERE id = %s", (account_id,))
            _audit(cur, actor, None, "member.deleted", "member", account_id,
                   {"name": name, "display_name": display}, _actor_ip(request))
        conn.commit()
        invalidate_cache()
        return {"ok": True, "id": account_id}
    finally:
        conn.close()


# ── Devices (replaces /tokens) ───────────────────────────────────────────────

@router.get("/devices")
async def list_devices(request: Request, owner_id: int | None = None):
    """List access_tokens as 'devices' with friendly metadata."""
    current_id = current_token_id(getattr(request.state, "access_token", None))
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT id, owner_id, label, token_prefix, device_type, device_name, "
                    "       last_ua, last_used_at, last_country, last_city, "
                    "       revoked_at, created_at "
                    "FROM access_tokens WHERE owner_id = %s ORDER BY id DESC",
                    (owner_id,),
                )
            else:
                cur.execute(
                    "SELECT id, owner_id, label, token_prefix, device_type, device_name, "
                    "       last_ua, last_used_at, last_country, last_city, "
                    "       revoked_at, created_at "
                    "FROM access_tokens ORDER BY id DESC"
                )
            rows = cur.fetchall()
            return [
                {
                    "id": r["id"],
                    "owner_id": r["owner_id"],
                    "label": r["label"],
                    "prefix": r["token_prefix"],
                    "device_type": r["device_type"] or "unknown",
                    "device_name": r["device_name"] or "Unknown device",
                    "last_ua": r["last_ua"],
                    "last_used_at": r["last_used_at"].isoformat() if r["last_used_at"] else None,
                    "last_country": r["last_country"],
                    "last_city": r["last_city"],
                    "revoked": r["revoked_at"] is not None,
                    "is_current": r["id"] == current_id,
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
    finally:
        conn.close()


@router.get("/devices/pending")
async def list_pending_devices():
    """Devices that accepted an invite but still await admin approval."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT t.id, t.owner_id, t.label, t.device_type, t.device_name, "
                "       t.last_ua, t.last_ip, t.last_country, t.last_city, "
                "       t.created_at, a.display_name, a.name "
                "FROM access_tokens t JOIN accounts a ON a.id = t.owner_id "
                "WHERE t.pending_approval = TRUE AND t.revoked_at IS NULL "
                "ORDER BY t.created_at DESC"
            )
            return [
                {
                    "id": r["id"],
                    "owner_id": r["owner_id"],
                    "owner_name": r["display_name"] or r["name"],
                    "label": r["label"],
                    "device_type": r["device_type"] or "unknown",
                    "device_name": r["device_name"] or "Unknown device",
                    "last_ua": r["last_ua"],
                    "last_ip": r["last_ip"],
                    "last_country": r["last_country"],
                    "last_city": r["last_city"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in cur.fetchall()
            ]
    finally:
        conn.close()


@router.post("/devices/{device_id}/approve")
async def approve_device(device_id: int, request: Request):
    """Admin approves a pending device — it can immediately authenticate."""
    actor = getattr(request.state, "owner_id", 1)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE access_tokens SET pending_approval = FALSE "
                "WHERE id = %s AND pending_approval = TRUE AND revoked_at IS NULL "
                "RETURNING owner_id, device_name",
                (device_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Device not found or not pending")
            owner_id, dev_name = row
            _audit(cur, actor, owner_id, "device.approved", "device", device_id,
                   {"device_name": dev_name}, _actor_ip(request))
        conn.commit()
        invalidate_cache()
        return {"ok": True, "id": device_id}
    finally:
        conn.close()


@router.patch("/devices/{device_id}")
async def rename_device(device_id: int, req: DeviceRename, request: Request):
    actor = getattr(request.state, "owner_id", 1)
    new_name = (req.device_name or "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="device_name is required")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE access_tokens SET device_name = %s WHERE id = %s RETURNING owner_id",
                (new_name, device_id),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Device not found")
            owner_id = row[0]
            _audit(cur, actor, owner_id, "device.renamed", "device", device_id,
                   {"new_name": new_name}, _actor_ip(request))
        conn.commit()
        return {"ok": True, "id": device_id, "device_name": new_name}
    finally:
        conn.close()


@router.post("/devices/{device_id}/sign-out")
async def sign_out_device(device_id: int, request: Request):
    """Soft-delete (revoke) a device's token.

    Refuses to sign out the device making the request — admins must do that
    by clearing the cookie in their own browser, not via API (defence
    against accidental self-lockout).
    """
    actor = getattr(request.state, "owner_id", 1)
    current_id = current_token_id(getattr(request.state, "access_token", None))
    if device_id == current_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot sign out the device you are currently using. "
                   "Log out from your browser instead.",
        )
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE access_tokens SET revoked_at = NOW() "
                "WHERE id = %s AND revoked_at IS NULL RETURNING owner_id, device_name",
                (device_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Device not found or already signed out")
            owner_id, dev_name = row
            _audit(cur, actor, owner_id, "device.signed_out", "device", device_id,
                   {"device_name": dev_name}, _actor_ip(request))
        conn.commit()
        invalidate_cache()
        return {"ok": True, "id": device_id}
    finally:
        conn.close()


# ── Invites ──────────────────────────────────────────────────────────────────

@router.post("/invites")
async def create_invite(req: InviteCreate, request: Request):
    """Generate a single-use invite link for a family member to add a device."""
    actor = getattr(request.state, "owner_id", 1)
    label = (req.label or "").strip() or None

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM accounts WHERE id = %s", (req.owner_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"owner_id {req.owner_id} does not exist")
            invite_uuid = uuid.uuid4().hex
            expires = datetime.now(timezone.utc) + timedelta(hours=INVITE_TTL_HOURS)
            cur.execute(
                "INSERT INTO family_invites "
                "(invite_uuid, owner_id, label, created_by, expires_at) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (invite_uuid, req.owner_id, label, actor, expires),
            )
            invite_id = cur.fetchone()[0]
            _audit(cur, actor, req.owner_id, "invite.created", "invite", invite_id,
                   {"label": label, "expires_at": expires.isoformat()}, _actor_ip(request))
        conn.commit()
        # Build the absolute URL the family member will open.
        host = request.headers.get("host", "127.0.0.1:1234")
        scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
        # The Flask app (the one serving /invite/<uuid>) listens on a different
        # port than the FastAPI host header here. We assume Flask is on 1234.
        # Override with X-Family-Web-Host header if reverse-proxied.
        web_host = request.headers.get("x-family-web-host")
        if web_host:
            url = f"{scheme}://{web_host}/invite/{invite_uuid}"
        else:
            # Strip FastAPI port (8400) and substitute Flask's 1234.
            host_no_port = host.split(":")[0]
            url = f"{scheme}://{host_no_port}:1234/invite/{invite_uuid}"
        return {
            "id": invite_id,
            "uuid": invite_uuid,
            "owner_id": req.owner_id,
            "label": label,
            "expires_at": expires.isoformat(),
            "ttl_hours": INVITE_TTL_HOURS,
            "url": url,
            "qr_svg": _qr_svg_for(url),
        }
    finally:
        conn.close()


@router.get("/invites")
async def list_invites(owner_id: int | None = None):
    """List pending (unused, unexpired) invites only."""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT id, invite_uuid, owner_id, label, expires_at, created_at "
                    "FROM family_invites "
                    "WHERE used_at IS NULL AND expires_at > NOW() AND owner_id = %s "
                    "ORDER BY created_at DESC",
                    (owner_id,),
                )
            else:
                cur.execute(
                    "SELECT id, invite_uuid, owner_id, label, expires_at, created_at "
                    "FROM family_invites "
                    "WHERE used_at IS NULL AND expires_at > NOW() "
                    "ORDER BY created_at DESC"
                )
            rows = cur.fetchall()
            return [
                {
                    "id": r["id"],
                    "uuid": r["invite_uuid"],
                    "owner_id": r["owner_id"],
                    "label": r["label"],
                    "expires_at": r["expires_at"].isoformat(),
                    "created_at": r["created_at"].isoformat(),
                }
                for r in rows
            ]
    finally:
        conn.close()


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: int, request: Request):
    """Mark a pending invite as used so the URL can't be redeemed."""
    actor = getattr(request.state, "owner_id", 1)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE family_invites SET used_at = NOW() "
                "WHERE id = %s AND used_at IS NULL RETURNING owner_id",
                (invite_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Invite not found or already used")
            _audit(cur, actor, row[0], "invite.revoked", "invite", invite_id,
                   {}, _actor_ip(request))
        conn.commit()
        return {"ok": True, "id": invite_id}
    finally:
        conn.close()


# ── Channel identities (Telegram / Discord / Withings) ───────────────────────

_ALLOWED_CHANNELS = {"telegram", "discord", "withings"}


@router.get("/channels")
async def list_channels(owner_id: int | None = None):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT id, owner_id, channel, external_id "
                    "FROM channel_identities WHERE owner_id = %s "
                    "ORDER BY channel, external_id",
                    (owner_id,),
                )
            else:
                cur.execute(
                    "SELECT id, owner_id, channel, external_id "
                    "FROM channel_identities ORDER BY owner_id, channel, external_id"
                )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


@router.post("/channels")
async def create_channel(req: ChannelCreate, request: Request):
    actor = getattr(request.state, "owner_id", 1)
    channel = (req.channel or "").strip().lower()
    if channel not in _ALLOWED_CHANNELS:
        raise HTTPException(status_code=400,
                            detail=f"channel must be one of {sorted(_ALLOWED_CHANNELS)}")
    external_id = (req.external_id or "").strip()
    if not external_id:
        raise HTTPException(status_code=400, detail="external_id is required")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM accounts WHERE id = %s", (req.owner_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"owner_id {req.owner_id} does not exist")
            try:
                cur.execute(
                    "INSERT INTO channel_identities (owner_id, channel, external_id) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (req.owner_id, channel, external_id),
                )
                new_id = cur.fetchone()[0]
            except Exception as e:
                conn.rollback()
                raise HTTPException(status_code=409, detail=f"already mapped or error: {e}")
            _audit(cur, actor, req.owner_id, "channel.added", "channel", new_id,
                   {"channel": channel, "external_id": external_id}, _actor_ip(request))
        conn.commit()
        invalidate_channel_cache(channel, external_id)
        return {"id": new_id, "owner_id": req.owner_id, "channel": channel, "external_id": external_id}
    finally:
        conn.close()


@router.delete("/channels/{channel_id}")
async def delete_channel(channel_id: int, request: Request):
    actor = getattr(request.state, "owner_id", 1)
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM channel_identities WHERE id = %s "
                "RETURNING owner_id, channel, external_id",
                (channel_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Channel mapping not found")
            _audit(cur, actor, row[0], "channel.removed", "channel", channel_id,
                   {"channel": row[1], "external_id": row[2]}, _actor_ip(request))
        conn.commit()
        invalidate_channel_cache(row[1], row[2])
        return {"ok": True, "id": channel_id}
    finally:
        conn.close()


# ── Activity feed ────────────────────────────────────────────────────────────

@router.get("/audit")
async def list_audit(limit: int = 10, offset: int = 0, owner_id: int | None = None):
    """Audit feed. Filter by owner_id to show only events targeting that member.

    Pagination: client requests pages with `?limit=N&offset=M`. Returns
    {'rows': [...], 'has_more': bool} so the UI knows whether to keep
    showing 'Load more'."""
    limit = max(1, min(int(limit or 10), 100))
    offset = max(0, int(offset or 0))
    # Fetch one extra to detect has_more without a second COUNT(*).
    fetch = limit + 1
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if owner_id is not None:
                cur.execute(
                    "SELECT a.id, a.actor_owner_id, a.target_owner_id, a.action, "
                    "       a.target_type, a.target_id, a.details, a.ip, a.at, "
                    "       ac.display_name AS actor_display, ac.name AS actor_name, "
                    "       tg.display_name AS target_display, tg.name AS target_name "
                    "FROM family_audit a "
                    "LEFT JOIN accounts ac ON ac.id = a.actor_owner_id "
                    "LEFT JOIN accounts tg ON tg.id = a.target_owner_id "
                    "WHERE a.target_owner_id = %s OR a.actor_owner_id = %s "
                    "ORDER BY a.at DESC LIMIT %s OFFSET %s",
                    (owner_id, owner_id, fetch, offset),
                )
            else:
                cur.execute(
                    "SELECT a.id, a.actor_owner_id, a.target_owner_id, a.action, "
                    "       a.target_type, a.target_id, a.details, a.ip, a.at, "
                    "       ac.display_name AS actor_display, ac.name AS actor_name, "
                    "       tg.display_name AS target_display, tg.name AS target_name "
                    "FROM family_audit a "
                    "LEFT JOIN accounts ac ON ac.id = a.actor_owner_id "
                    "LEFT JOIN accounts tg ON tg.id = a.target_owner_id "
                    "ORDER BY a.at DESC LIMIT %s OFFSET %s",
                    (fetch, offset),
                )
            raw = cur.fetchall()
            has_more = len(raw) > limit
            rows = raw[:limit]
            return {
                "rows": [
                    {
                        "id": r["id"],
                        "action": r["action"],
                        "actor": r["actor_display"] or r["actor_name"],
                        "target": r["target_display"] or r["target_name"],
                        "target_type": r["target_type"],
                        "target_id": r["target_id"],
                        "details": r["details"] or {},
                        "ip": r["ip"],
                        "at": r["at"].isoformat() if r["at"] else None,
                    }
                    for r in rows
                ],
                "has_more": has_more,
                "offset": offset,
                "limit": limit,
            }
    finally:
        conn.close()
