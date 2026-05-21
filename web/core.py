
from flask import Blueprint, g, render_template, jsonify, redirect, send_from_directory, url_for
from web._helpers import get_conn, _serialize, IMG_DIR, DB_NAME
from agent.core.identity import DEFAULT_OWNER_ID

core_bp = Blueprint("core", __name__)


def _owner_id() -> int:
    return getattr(g, "owner_id", DEFAULT_OWNER_ID)


@core_bp.route("/img/<path:filename>")
def serve_img(filename):
    mimetype = "application/manifest+json" if filename.endswith(".webmanifest") else None
    return send_from_directory(IMG_DIR, filename, mimetype=mimetype)


@core_bp.route("/")
def index():
    return redirect(url_for("chat.chat"))


@core_bp.route("/profile")
def profile():
    return render_template("profile.html", db_name=DB_NAME)


@core_bp.route("/api/stats")
def api_stats():
    owner_id = _owner_id()
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT session_id) FROM raw_conversations WHERE owner_id = %s", (owner_id,))
        sessions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations WHERE rejected = false AND owner_id = %s", (owner_id,))
        observations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE end_time IS NULL AND human_end_time IS NULL AND layer='confirmed' AND rejected = false AND owner_id = %s", (owner_id,))
        confirmed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE end_time IS NULL AND human_end_time IS NULL AND layer='suspected' AND rejected = false AND owner_id = %s", (owner_id,))
        suspected = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE rejected = false AND (end_time IS NOT NULL OR human_end_time IS NOT NULL) AND owner_id = %s", (owner_id,))
        closed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE superseded_by IS NOT NULL AND end_time IS NULL AND human_end_time IS NULL AND owner_id = %s", (owner_id,))
        disputes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM relationships WHERE status='active' AND owner_id = %s", (owner_id,))
        relationships = cur.fetchone()[0]
        return jsonify({
            "sessions": sessions,
            "observations": observations,
            "confirmed": confirmed,
            "suspected": suspected,
            "closed": closed,
            "disputes": disputes,
            "relationships": relationships,
        })
    finally:
        conn.close()


@core_bp.route("/api/categories")
def api_categories():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT category FROM user_profile "
            "WHERE end_time IS NULL AND rejected = false AND human_end_time IS NULL "
            "AND owner_id = %s ORDER BY category",
            (_owner_id(),),
        )
        return jsonify([row[0] for row in cur.fetchall()])
    finally:
        conn.close()
