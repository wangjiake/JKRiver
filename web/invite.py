"""Invite-link flow — public landing page + accept endpoint.

Flow:
  1. Admin (logged in elsewhere) calls FastAPI POST /api/family/invites,
     which inserts a row in family_invites with a random invite_uuid.
  2. Admin shares the URL  http://<host>:1234/invite/<uuid>  with the family
     member via WhatsApp / message / scanning a QR code.
  3. Family member opens the URL on their device → they see this page,
     which is OUTSIDE the auth_bp gate (registered in web/__init__.py so
     auth.before_request must allow it).
  4. They give the device a name and click Accept → we mint a fresh
     access_tokens row, set the cookie, redirect to /chat.

The invite_uuid is single-use; we mark `used_at` on accept so the same link
can't be replayed.
"""

import secrets
from datetime import datetime, timezone

from flask import Blueprint, make_response, redirect, render_template, request, url_for

from agent.config import load_config
from agent.core.identity import (
    detect_device_name, detect_device_type, hash_token, token_prefix,
)
from agent.storage._db import get_db_connection

invite_bp = Blueprint("invite", __name__)

COOKIE_NAME = "jkriver_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def _require_admin_approval() -> bool:
    """When True, accepted invites land in pending_approval=TRUE state until
    an admin explicitly approves them on the system page."""
    try:
        return bool((load_config().get("family", {}) or {}).get("require_admin_approval", False))
    except Exception:
        return False


def _record_audit(cur, actor, target_owner_id, action, target_type, target_id,
                  details, ip):
    import json
    cur.execute(
        "INSERT INTO family_audit "
        "(actor_owner_id, target_owner_id, action, target_type, target_id, details, ip) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (actor, target_owner_id, action, target_type, target_id,
         json.dumps(details or {}, ensure_ascii=False), ip),
    )


@invite_bp.route("/invite/<invite_uuid>", methods=["GET"])
def invite_landing(invite_uuid: str):
    """Show the 'You're invited' page. No auth required."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT i.id, i.owner_id, i.label, i.expires_at, i.used_at, "
                "       a.name, a.display_name "
                "FROM family_invites i JOIN accounts a ON a.id = i.owner_id "
                "WHERE i.invite_uuid = %s",
                (invite_uuid,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return render_template("invite.html", error="not_found", invite_uuid=invite_uuid)
    invite_id, owner_id, label, expires_at, used_at, name, display = row
    if used_at is not None:
        return render_template("invite.html", error="already_used", invite_uuid=invite_uuid)
    if expires_at and expires_at < datetime.now(timezone.utc):
        return render_template("invite.html", error="expired", invite_uuid=invite_uuid)

    suggested = detect_device_name(request.headers.get("User-Agent"))
    return render_template(
        "invite.html",
        invite_uuid=invite_uuid,
        owner_name=display or name,
        owner_id=owner_id,
        label=label,
        suggested_device=suggested,
        error=None,
    )


@invite_bp.route("/invite/<invite_uuid>", methods=["POST"])
def invite_accept(invite_uuid: str):
    """Consume the invite: mint a token, set the cookie, redirect to /chat."""
    ua = request.headers.get("User-Agent")
    ip = request.remote_addr
    device_name = (request.form.get("device_name") or "").strip() or detect_device_name(ua)
    device_type = detect_device_type(ua)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Atomically mark the invite used (single-use guard).
            cur.execute(
                "UPDATE family_invites SET used_at = NOW() "
                "WHERE invite_uuid = %s AND used_at IS NULL "
                "  AND (expires_at IS NULL OR expires_at > NOW()) "
                "RETURNING id, owner_id, label",
                (invite_uuid,),
            )
            row = cur.fetchone()
            if not row:
                conn.rollback()
                return render_template("invite.html", error="already_used", invite_uuid=invite_uuid), 410
            invite_id, owner_id, label = row

            new_token = "jk_" + secrets.token_urlsafe(24)
            th = hash_token(new_token)
            tp = token_prefix(new_token)
            needs_approval = _require_admin_approval()

            cur.execute(
                "INSERT INTO access_tokens "
                "(token, token_hash, token_prefix, owner_id, label, "
                " device_type, device_name, last_ua, last_ip, last_used_at, "
                " pending_approval) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s) "
                "RETURNING id",
                (new_token, th, tp, owner_id, label, device_type, device_name,
                 ua, ip, needs_approval),
            )
            token_id = cur.fetchone()[0]
            _record_audit(cur, owner_id, owner_id,
                          "invite.accepted" if not needs_approval else "device.pending_approval",
                          "device", token_id,
                          {"device_name": device_name, "device_type": device_type,
                           "invite_id": invite_id}, ip)
        conn.commit()
    finally:
        conn.close()

    if needs_approval:
        # Set cookie so the waiting page can identify the device, but don't
        # send the user to /chat yet — they'll see a "waiting for admin"
        # screen that polls and auto-redirects when approved.
        resp = make_response(redirect(url_for("invite.invite_waiting", token_id=token_id)))
        resp.set_cookie(COOKIE_NAME, new_token, max_age=COOKIE_MAX_AGE,
                        httponly=False, samesite="Lax")
        return resp

    resp = make_response(redirect(url_for("chat.chat")))
    resp.set_cookie(COOKIE_NAME, new_token, max_age=COOKIE_MAX_AGE, httponly=False, samesite="Lax")
    return resp


@invite_bp.route("/invite/waiting/<int:token_id>")
def invite_waiting(token_id: int):
    """Page family member sees after accepting an invite while admin approval
    is required. Renders a 'waiting for admin to approve' screen with a
    meta-refresh that polls the approval state every 5s.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT t.pending_approval, t.revoked_at, t.device_name, "
                "       a.display_name, a.name "
                "FROM access_tokens t JOIN accounts a ON a.id = t.owner_id "
                "WHERE t.id = %s",
                (token_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return render_template("invite.html", error="not_found", invite_uuid=""), 404
    pending, revoked, device_name, display, name = row
    if revoked is not None:
        return render_template("invite_waiting.html", state="revoked",
                               device_name=device_name, owner_name=display or name)
    if not pending:
        # Approved — bounce to /chat.
        return redirect(url_for("chat.chat"))
    return render_template("invite_waiting.html", state="pending",
                           device_name=device_name, owner_name=display or name,
                           token_id=token_id)


@invite_bp.route("/invite/waiting/<int:token_id>/status")
def invite_waiting_status(token_id: int):
    """JSON poll endpoint for the waiting page. Returns {'state': 'pending'|
    'approved'|'revoked'} so a frontend (or meta-refresh) can react."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pending_approval, revoked_at FROM access_tokens WHERE id = %s",
                (token_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {"state": "not_found"}, 404
    pending, revoked = row
    if revoked is not None:
        return {"state": "revoked"}
    return {"state": "pending" if pending else "approved"}
