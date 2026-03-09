
from datetime import datetime, date, timezone
from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor
from web._helpers import get_conn, _serialize, _log_review

review_bp = Blueprint("review", __name__)


@review_bp.route("/api/review/profile", methods=["POST"])
def api_review_profile():
    data = request.get_json(force=True)
    fact_id = data.get("id")
    action = data.get("action")
    note = data.get("note", "")
    human_end_time = data.get("human_end_time")

    if not fact_id or action not in ("reject", "unreject", "close", "reopen"):
        return jsonify({"error": "Invalid parameters"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, rejected, human_end_time, end_time, note FROM user_profile WHERE id = %s", (fact_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Record not found"}), 404

        old_value = {k: _serialize(v) if isinstance(v, (datetime, date)) else v for k, v in row.items()}

        if action == "reject":
            cur.execute(
                "UPDATE user_profile SET rejected = true, note = %s WHERE id = %s",
                (note or row["note"], fact_id),
            )
            new_value = {"rejected": True, "note": note}

        elif action == "unreject":
            cur.execute(
                "UPDATE user_profile SET rejected = false, note = %s WHERE id = %s",
                (note or None, fact_id),
            )
            new_value = {"rejected": False, "note": note}

        elif action == "close":
            if human_end_time:
                try:
                    het = datetime.fromisoformat(human_end_time)
                except (ValueError, TypeError):
                    return jsonify({"error": "Invalid time format"}), 400
            else:
                het = datetime.now(timezone.utc)
            cur.execute(
                "UPDATE user_profile SET human_end_time = %s, note = %s WHERE id = %s",
                (het, note or row["note"], fact_id),
            )
            new_value = {"human_end_time": het.isoformat(), "note": note}

        elif action == "reopen":
            cur.execute(
                "UPDATE user_profile SET human_end_time = NULL, note = %s WHERE id = %s",
                (note or None, fact_id),
            )
            new_value = {"human_end_time": None, "note": note}

        _log_review(conn, "user_profile", fact_id, action, old_value, new_value, note)
        conn.commit()
        return jsonify({"ok": True, "action": action, "id": fact_id})
    finally:
        conn.close()


@review_bp.route("/api/review/observation", methods=["POST"])
def api_review_observation():
    data = request.get_json(force=True)
    obs_id = data.get("id")
    action = data.get("action")
    note = data.get("note", "")

    if not obs_id or action not in ("reject", "unreject"):
        return jsonify({"error": "Invalid parameters"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, rejected, note FROM observations WHERE id = %s", (obs_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Record not found"}), 404

        old_value = dict(row)

        if action == "reject":
            cur.execute(
                "UPDATE observations SET rejected = true, note = %s WHERE id = %s",
                (note or row["note"], obs_id),
            )
            new_value = {"rejected": True, "note": note}
        else:
            cur.execute(
                "UPDATE observations SET rejected = false, note = %s WHERE id = %s",
                (note or None, obs_id),
            )
            new_value = {"rejected": False, "note": note}

        _log_review(conn, "observations", obs_id, action, old_value, new_value, note)
        conn.commit()
        return jsonify({"ok": True, "action": action, "id": obs_id})
    finally:
        conn.close()


@review_bp.route("/api/review/log")
def api_review_log():
    target_table = request.args.get("table")
    target_id = request.args.get("id")
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = []
        params = []
        if target_table:
            conditions.append("target_table = %s")
            params.append(target_table)
        if target_id:
            conditions.append("target_id = %s")
            params.append(int(target_id))
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"SELECT id, target_table, target_id, action, old_value, new_value, note, created_at "
            f"FROM review_log {where} "
            f"ORDER BY created_at DESC LIMIT 100",
            params,
        )
        rows = cur.fetchall()
        return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                         for k, v in row.items()} for row in rows])
    finally:
        conn.close()
