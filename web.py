
import os
import sys
import json
import logging
import argparse
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from flask import Flask, render_template, jsonify, request, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

from agent.config import load_config as _load_config
from agent.storage import get_db_connection

_config = _load_config()
_db_cfg = _config.get("database", {})
DB_NAME = _db_cfg.get("name", "Riverse")
DB_USER = _db_cfg.get("user", "postgres")
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img")

def get_conn():
    return get_db_connection()

def _serialize(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

@app.route("/img/<path:filename>")
def serve_img(filename):
    return send_from_directory(IMG_DIR, filename)

@app.route("/")
def index():
    return render_template("profile.html", db_name=DB_NAME)

@app.route("/api/stats")
def api_stats():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT session_id) FROM raw_conversations")
        sessions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM observations WHERE rejected = false")
        observations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE end_time IS NULL AND human_end_time IS NULL AND layer='confirmed' AND rejected = false")
        confirmed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE end_time IS NULL AND human_end_time IS NULL AND layer='suspected' AND rejected = false")
        suspected = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE rejected = false AND (end_time IS NOT NULL OR human_end_time IS NOT NULL)")
        closed = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM user_profile WHERE superseded_by IS NOT NULL AND end_time IS NULL AND human_end_time IS NULL")
        disputes = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM relationships WHERE status='active'")
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

@app.route("/api/profile")
def api_profile():
    category = request.args.get("category")
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = ["end_time IS NULL"]
        params = []
        if category:
            conditions.append("category = %s")
            params.append(category)
        where = "WHERE " + " AND ".join(conditions)
        cur.execute(
            f"SELECT id, category, subject, value, layer, source_type, "
            f"start_time, decay_days, expires_at, evidence, mention_count, "
            f"created_at, updated_at, confirmed_at, superseded_by, supersedes, "
            f"rejected, human_end_time, note "
            f"FROM user_profile {where} "
            f"ORDER BY rejected ASC, "
            f"CASE layer WHEN 'confirmed' THEN 1 WHEN 'suspected' THEN 2 END, "
            f"category, subject",
            params,
        )
        rows = cur.fetchall()
        return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                         for k, v in row.items()} for row in rows])
    finally:
        conn.close()

@app.route("/api/categories")
def api_categories():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT category FROM user_profile WHERE end_time IS NULL AND rejected = false AND human_end_time IS NULL ORDER BY category"
        )
        return jsonify([row[0] for row in cur.fetchall()])
    finally:
        conn.close()

@app.route("/api/timeline")
def api_timeline():
    category = request.args.get("category")
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = []
        params = []
        if category:
            conditions.append("category = %s")
            params.append(category)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"SELECT id, category, subject, value, layer, source_type, "
            f"start_time, end_time, mention_count, superseded_by, supersedes, "
            f"rejected, human_end_time, note "
            f"FROM user_profile {where} "
            f"ORDER BY category, subject, start_time",
            params,
        )
        rows = cur.fetchall()
        return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                         for k, v in row.items()} for row in rows])
    finally:
        conn.close()

@app.route("/api/relationships")
def api_relationships():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT id, name, relation, details, mention_count, "
            "first_mentioned_at, last_mentioned_at "
            "FROM relationships WHERE status = 'active' "
            "ORDER BY last_mentioned_at DESC"
        )
        rows = cur.fetchall()
        return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                         for k, v in row.items()} for row in rows])
    finally:
        conn.close()

@app.route("/api/trajectory")
def api_trajectory():
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM trajectory_summary ORDER BY updated_at DESC LIMIT 1")
        row = cur.fetchone()
        if row:
            return jsonify({k: _serialize(v) if isinstance(v, (datetime, date)) else v
                            for k, v in row.items()})
        return jsonify(None)
    finally:
        conn.close()

@app.route("/api/snapshot")
def api_snapshot():
    month = request.args.get("month", "")
    if not month:
        return jsonify([])
    try:
        year, mon = month.split("-")
        year, mon = int(year), int(mon)
        if mon == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, mon + 1, 1)
        month_end = next_month - timedelta(seconds=1)
        month_start = datetime(year, mon, 1)
    except Exception:
        return jsonify([])

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

@app.route("/api/snapshot/months")
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

@app.route("/api/observations")
def api_observations():
    obs_type = request.args.get("type")
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        conditions = []
        params = []
        if obs_type:
            conditions.append("observation_type = %s")
            params.append(obs_type)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"SELECT id, session_id, observation_type, content, subject, context, created_at, "
            f"rejected, note "
            f"FROM observations {where} "
            f"ORDER BY rejected ASC, created_at DESC",
            params,
        )
        rows = cur.fetchall()
        return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                         for k, v in row.items()} for row in rows])
    finally:
        conn.close()

def _log_review(conn, target_table, target_id, action, old_value, new_value, note):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO review_log (target_table, target_id, action, old_value, new_value, note) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (target_table, target_id, action,
             json.dumps(old_value, default=_serialize, ensure_ascii=False) if old_value else None,
             json.dumps(new_value, default=_serialize, ensure_ascii=False) if new_value else None,
             note),
        )

@app.route("/api/review/profile", methods=["POST"])
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
                het = datetime.now()
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

@app.route("/api/review/observation", methods=["POST"])
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

@app.route("/api/review/log")
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

@app.route("/finance")
def finance_page():
    return render_template("finance.html", db_name=DB_NAME)

@app.route("/api/finance/overview")
def api_finance_overview():
    from agent.storage import get_finance_overview
    data = get_finance_overview()
    return jsonify(data)

@app.route("/api/finance/transactions")
def api_finance_transactions():
    from agent.storage import load_finance_transactions
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    day = request.args.get("day", type=int)
    category = request.args.get("category")
    merchant = request.args.get("merchant")
    limit = request.args.get("limit", 100, type=int)
    offset = request.args.get("offset", 0, type=int)
    rows = load_finance_transactions(
        year=year, month=month, day=day,
        category=category, merchant=merchant,
        limit=limit, offset=offset,
    )
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/finance/summary")
def api_finance_summary():
    from agent.storage import get_finance_summary
    group_by = request.args.get("group_by", "month")
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    rows = get_finance_summary(group_by=group_by, year=year, month=month)
    result = []
    for row in rows:
        item = {k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                for k, v in row.items() if k != "categories"}
        item["categories"] = [
            {ck: _serialize(cv) if isinstance(cv, (datetime, date, Decimal)) else cv
             for ck, cv in cat.items()}
            for cat in row.get("categories", [])
        ]
        result.append(item)
    return jsonify(result)

@app.route("/api/finance/merchants")
def api_finance_merchants():
    from agent.storage import get_finance_merchant_stats
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    limit = request.args.get("limit", 20, type=int)
    rows = get_finance_merchant_stats(year=year, month=month, limit=limit)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/finance/categories")
def api_finance_categories():
    from agent.storage import get_finance_category_stats
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    rows = get_finance_category_stats(year=year, month=month)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/finance/import", methods=["POST"])
def api_finance_import():
    import yaml
    from agent.tools._mcp_bridge import MCPManager

    data = request.get_json(force=True)
    action = data.get("action", "import_all")
    after = data.get("after", "")

    from agent.storage import (import_finance_from_email,
                                get_last_import_date,
                                get_imported_email_ids)

    if not after:
        after = get_last_import_date() or "2025/01/01"

    cfg = _load_config()

    mcp_servers = cfg.get("mcp", {}).get("servers", [])
    gmail_cfg = None
    for s in mcp_servers:
        if s.get("name") == "gmail":
            gmail_cfg = s
            break

    if not gmail_cfg:
        return jsonify({"error": "Gmail MCP not configured"}), 500

    manager = None
    try:
        manager = MCPManager([gmail_cfg])

        query = f"from:noreply@example.com after:{after}"
        search_result = manager.call_tool("gmail", "search_emails", {
            "query": query, "maxResults": 100
        })

        import re as _re
        email_ids = _re.findall(r'^ID:\s*(\S+)', search_result, _re.MULTILINE)

        existing_ids = get_imported_email_ids()
        new_ids = [eid for eid in email_ids if eid not in existing_ids]
        skipped = len(email_ids) - len(new_ids)

        results = {
            "imported": 0, "duplicates": skipped,
            "failed": 0, "details": [],
            "searched": len(email_ids), "skipped": skipped,
            "after": after,
        }

        for email_id in new_ids:
            try:
                email_text = manager.call_tool("gmail", "read_email", {
                    "messageId": email_id
                })

                subj_match = _re.search(r'^Subject:\s*(.+)', email_text, _re.MULTILINE)
                subject = subj_match.group(1).strip() if subj_match else ""

                result = import_finance_from_email(email_id, subject, email_text)

                if result["success"]:
                    results["imported"] += 1
                elif result["duplicate"]:
                    results["duplicates"] += 1
                else:
                    results["failed"] += 1

                results["details"].append({
                    "email_id": email_id,
                    "subject": subject[:60],
                    **{k: v for k, v in result.items()
                       if k not in ("parsed",)},
                })
            except Exception as e:
                results["failed"] += 1
                results["details"].append({
                    "email_id": email_id,
                    "success": False,
                    "error": str(e),
                })

        return jsonify(results)

    except Exception as e:
        logging.exception("Finance import error")
        return jsonify({"error": str(e)}), 500
    finally:
        if manager:
            try:
                manager.shutdown()
            except Exception:
                pass

@app.route("/api/finance/transaction/<int:txn_id>", methods=["PUT"])
def api_finance_update_transaction(txn_id):
    from agent.storage import update_finance_transaction
    data = request.get_json(force=True)
    category = data.get("category")
    note = data.get("note")
    ok = update_finance_transaction(txn_id, category=category, note=note)
    if ok:
        return jsonify({"ok": True, "id": txn_id})
    return jsonify({"error": "Record not found or no updates"}), 404

@app.route("/api/finance/merchant-categories")
def api_finance_merchant_categories_get():
    from agent.storage import load_merchant_categories
    rows = load_merchant_categories()
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/finance/merchant-categories", methods=["POST"])
def api_finance_merchant_categories_post():
    from agent.storage import save_merchant_category
    data = request.get_json(force=True)
    pattern = data.get("merchant_pattern", "").strip()
    category = data.get("category", "").strip()
    if not pattern or not category:
        return jsonify({"error": "Parameters cannot be empty"}), 400
    mid = save_merchant_category(pattern, category)
    return jsonify({"ok": True, "id": mid})

def _load_withings_config():
    return _load_config().get("withings", {})

@app.route("/health")
def health_page():
    return render_template("health.html", db_name=DB_NAME)

@app.route("/api/health/overview")
def api_health_overview():
    from agent.storage import get_health_overview
    data = get_health_overview()
    return jsonify(data)

@app.route("/api/health/measures")
def api_health_measures():
    from agent.storage import load_withings_measures
    measure_type = request.args.get("type", type=int)
    days = request.args.get("days", 90, type=int)
    rows = load_withings_measures(measure_type=measure_type, days=days)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/health/activity")
def api_health_activity():
    from agent.storage import load_withings_activity
    days = request.args.get("days", 90, type=int)
    rows = load_withings_activity(days=days)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/health/sleep")
def api_health_sleep():
    from agent.storage import load_withings_sleep
    days = request.args.get("days", 90, type=int)
    rows = load_withings_sleep(days=days)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])

@app.route("/api/health/authorize")
def api_health_authorize():
    from agent.withings_client import get_authorize_url
    cfg = _load_withings_config()
    url = get_authorize_url(
        client_id=cfg["client_id"],
        callback_url=cfg["callback_url"],
        scopes=cfg.get("scopes", "user.activity,user.metrics,user.info"),
    )
    return jsonify({"url": url})

@app.route("/callback/withings", methods=["GET", "POST"])
def callback_withings():
    code = request.args.get("code") or request.form.get("code")
    if not code:
        return "Missing code parameter", 400
    try:
        from agent.withings_client import exchange_code
        from agent.storage import save_withings_tokens
        cfg = _load_withings_config()
        tokens = exchange_code(
            client_id=cfg["client_id"],
            consumer_secret=cfg["consumer_secret"],
            code=code,
            callback_url=cfg["callback_url"],
        )
        save_withings_tokens(
            user_id=tokens["userid"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens["expires_in"],
            scope=tokens.get("scope", ""),
        )
        from flask import redirect
        return redirect("/health")
    except Exception as e:
        logging.exception("Withings OAuth callback error")
        return f"OAuth error: {e}", 500

@app.route("/api/health/exchange-code", methods=["POST"])
def api_health_exchange_code():
    import re as _re
    data = request.get_json(force=True)
    code_or_url = data.get("code", "").strip()
    if not code_or_url:
        return jsonify({"error": "Missing code"}), 400

    match = _re.search(r'[?&]code=([^&]+)', code_or_url)
    code = match.group(1) if match else code_or_url

    try:
        from agent.withings_client import exchange_code
        from agent.storage import save_withings_tokens
        cfg = _load_withings_config()
        tokens = exchange_code(
            client_id=cfg["client_id"],
            consumer_secret=cfg["consumer_secret"],
            code=code,
            callback_url=cfg["callback_url"],
        )
        save_withings_tokens(
            user_id=tokens["userid"],
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_in=tokens["expires_in"],
            scope=tokens.get("scope", ""),
        )
        return jsonify({"ok": True, "userid": tokens["userid"]})
    except Exception as e:
        logging.exception("Withings code exchange error")
        return jsonify({"error": str(e)}), 500

@app.route("/api/health/sync", methods=["POST"])
def api_health_sync():
    from agent.storage import (
        load_withings_tokens, save_withings_tokens,
        save_withings_measure, save_withings_activity, save_withings_sleep,
        get_last_sync_time, save_sync_log,
    )
    from agent.withings_client import (
        refresh_tokens, get_measures, get_activity, get_sleep_summary,
        convert_measure_value, MEASURE_TYPES,
    )

    data = request.get_json(force=True)
    sync_type = data.get("type", "all")
    force_full = data.get("full", False)

    tokens = load_withings_tokens()
    if not tokens:
        return jsonify({"error": "Not connected. Please authorize first."}), 400

    cfg = _load_withings_config()
    now = datetime.now(timezone.utc)

    expires_at = tokens["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        try:
            new_tokens = refresh_tokens(
                client_id=cfg["client_id"],
                consumer_secret=cfg["consumer_secret"],
                refresh_token=tokens["refresh_token"],
            )
            save_withings_tokens(
                user_id=new_tokens["userid"] or tokens["user_id"],
                access_token=new_tokens["access_token"],
                refresh_token=new_tokens["refresh_token"],
                expires_in=new_tokens["expires_in"],
                scope=new_tokens.get("scope", ""),
            )
            tokens["access_token"] = new_tokens["access_token"]
        except Exception as e:
            return jsonify({"error": f"Token refresh failed: {e}"}), 500

    access_token = tokens["access_token"]
    results = {}

    if sync_type in ("all", "measures"):
        try:
            last_sync = get_last_sync_time("measures") if not force_full else None
            if last_sync:
                start_ts = int(last_sync.timestamp())
            else:
                start_ts = int((now - timedelta(days=365)).timestamp())
            end_ts = int(now.timestamp())

            body = get_measures(access_token, start_ts, end_ts)
            count = 0
            for grp in body.get("measuregrps", []):
                grpid = grp["grpid"]
                measured_at = datetime.fromtimestamp(grp["date"])
                source = grp.get("attrib")
                for m in grp.get("measures", []):
                    mtype = m["type"]
                    raw_val = m["value"]
                    unit_exp = m["unit"]
                    converted = convert_measure_value(raw_val, unit_exp)
                    type_info = MEASURE_TYPES.get(mtype)
                    unit_label = type_info[1] if type_info else None
                    save_withings_measure(
                        grpid=grpid, measured_at=measured_at,
                        measure_type=mtype, value=converted,
                        unit=unit_label, source=source,
                    )
                    count += 1
            save_sync_log("measures", count)
            results["measures"] = {"synced": count}
        except Exception as e:
            save_sync_log("measures", 0, str(e))
            results["measures"] = {"error": str(e)}

    if sync_type in ("all", "activity"):
        try:
            last_sync = get_last_sync_time("activity") if not force_full else None
            if last_sync:
                start_ymd = last_sync.strftime("%Y-%m-%d")
            else:
                start_ymd = (now - timedelta(days=365)).strftime("%Y-%m-%d")
            end_ymd = now.strftime("%Y-%m-%d")

            body = get_activity(access_token, start_ymd, end_ymd)
            count = 0
            for act in body.get("activities", []):
                save_withings_activity(
                    activity_date=act["date"],
                    steps=act.get("steps"),
                    distance=act.get("distance"),
                    calories=act.get("totalcalories"),
                    active_calories=act.get("calories"),
                    soft_duration=act.get("soft"),
                    moderate_duration=act.get("moderate"),
                    intense_duration=act.get("intense"),
                )
                count += 1
            save_sync_log("activity", count)
            results["activity"] = {"synced": count}
        except Exception as e:
            save_sync_log("activity", 0, str(e))
            results["activity"] = {"error": str(e)}

    if sync_type in ("all", "sleep"):
        try:
            last_sync = get_last_sync_time("sleep") if not force_full else None
            if last_sync:
                start_ymd = last_sync.strftime("%Y-%m-%d")
            else:
                start_ymd = (now - timedelta(days=365)).strftime("%Y-%m-%d")
            end_ymd = now.strftime("%Y-%m-%d")

            body = get_sleep_summary(access_token, start_ymd, end_ymd)
            count = 0
            for s in body.get("series", []):
                sleep_data = s.get("data", {})
                save_withings_sleep(
                    sleep_date=s.get("date", s.get("startdate", "")[:10]),
                    start_time=s.get("startdate"),
                    end_time=s.get("enddate"),
                    duration_seconds=sleep_data.get("total_sleep_time") or sleep_data.get("total_timeinbed"),
                    deep_sleep_seconds=sleep_data.get("deepsleepduration"),
                    light_sleep_seconds=sleep_data.get("lightsleepduration"),
                    rem_sleep_seconds=sleep_data.get("remsleepduration"),
                    awake_seconds=sleep_data.get("wakeupcount"),
                    wakeup_count=sleep_data.get("nb_wakeup") or sleep_data.get("wakeupcount"),
                    sleep_score=sleep_data.get("sleep_score"),
                    hr_average=sleep_data.get("hr_average"),
                    hr_min=sleep_data.get("hr_min"),
                    rr_average=sleep_data.get("rr_average"),
                )
                count += 1
            save_sync_log("sleep", count)
            results["sleep"] = {"synced": count}
        except Exception as e:
            save_sync_log("sleep", 0, str(e))
            results["sleep"] = {"error": str(e)}

    return jsonify(results)

@app.route("/api/health/debug-raw")
def api_health_debug_raw():
    from agent.storage import load_withings_tokens
    from agent.withings_client import get_sleep_summary, get_activity

    tokens = load_withings_tokens()
    if not tokens:
        return jsonify({"error": "Not connected"}), 400

    access_token = tokens["access_token"]
    data_type = request.args.get("type", "sleep")
    days = request.args.get("days", 90, type=int)
    now = datetime.now(timezone.utc)
    start_ymd = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    end_ymd = now.strftime("%Y-%m-%d")

    try:
        if data_type == "sleep":
            body = get_sleep_summary(access_token, start_ymd, end_ymd)
        else:
            body = get_activity(access_token, start_ymd, end_ymd)
        return jsonify({"start": start_ymd, "end": end_ymd, "body": body})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Profile dashboard web server")
    parser.add_argument("--port", type=int, default=1234, help="Port (default: 1234)")
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port, debug=False)
