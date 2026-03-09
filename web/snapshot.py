
from datetime import datetime, date, timedelta, timezone
from flask import Blueprint, jsonify, request
from psycopg2.extras import RealDictCursor
from web._helpers import get_conn, _serialize

snapshot_bp = Blueprint("snapshot", __name__)


@snapshot_bp.route("/api/snapshot")
def api_snapshot():
    month = request.args.get("month", "")
    if not month:
        return jsonify([])
    try:
        year, mon = month.split("-")
        year, mon = int(year), int(mon)
        if mon == 12:
            next_month = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month = datetime(year, mon + 1, 1, tzinfo=timezone.utc)
        month_end = next_month - timedelta(seconds=1)
        month_start = datetime(year, mon, 1, tzinfo=timezone.utc)
    except Exception:
        return jsonify({"error": "Invalid month format, expected YYYY-MM"}), 400

    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, category, subject, value, layer, source_type, "
            "start_time, end_time, mention_count, superseded_by, "
            "(start_time >= %s AND start_time <= %s) AS is_new "
            "FROM user_profile "
            "WHERE start_time <= %s "
            "AND (end_time IS NULL OR end_time > %s) "
            "ORDER BY CASE layer WHEN 'confirmed' THEN 1 WHEN 'suspected' THEN 2 END, "
            "category, subject",
            (month_start, month_end, month_end, month_end),
        )
        rows = cur.fetchall()
        return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                         for k, v in row.items()} for row in rows])
    finally:
        conn.close()


@snapshot_bp.route("/api/snapshot/months")
def api_snapshot_months():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT TO_CHAR(start_time, 'YYYY-MM') as m "
            "FROM user_profile WHERE start_time IS NOT NULL "
            "ORDER BY m"
        )
        months = [row[0] for row in cur.fetchall()]
        return jsonify(months)
    finally:
        conn.close()
