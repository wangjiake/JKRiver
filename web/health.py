
import logging
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from flask import Blueprint, render_template, jsonify, request
from web._helpers import _serialize, DB_NAME, load_config as _load_config

health_bp = Blueprint("health", __name__)


def _load_withings_config():
    return _load_config().get("withings", {})


@health_bp.route("/health")
def health_page():
    return render_template("health.html", db_name=DB_NAME)


@health_bp.route("/api/health/overview")
def api_health_overview():
    from agent.storage import get_health_overview
    data = get_health_overview()
    return jsonify(data)


@health_bp.route("/api/health/measures")
def api_health_measures():
    from agent.storage import load_withings_measures
    measure_type = request.args.get("type", type=int)
    days = request.args.get("days", 90, type=int)
    rows = load_withings_measures(measure_type=measure_type, days=days)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])


@health_bp.route("/api/health/activity")
def api_health_activity():
    from agent.storage import load_withings_activity
    days = request.args.get("days", 90, type=int)
    rows = load_withings_activity(days=days)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])


@health_bp.route("/api/health/sleep")
def api_health_sleep():
    from agent.storage import load_withings_sleep
    days = request.args.get("days", 90, type=int)
    rows = load_withings_sleep(days=days)
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])


@health_bp.route("/api/health/authorize")
def api_health_authorize():
    from agent.withings_client import get_authorize_url
    cfg = _load_withings_config()
    url = get_authorize_url(
        client_id=cfg["client_id"],
        callback_url=cfg["callback_url"],
        scopes=cfg.get("scopes", "user.activity,user.metrics,user.info"),
    )
    return jsonify({"url": url})


@health_bp.route("/callback/withings", methods=["GET", "POST"])
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


@health_bp.route("/api/health/exchange-code", methods=["POST"])
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


@health_bp.route("/api/health/sync", methods=["POST"])
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
                measured_at = datetime.fromtimestamp(grp["date"], tz=timezone.utc)
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


@health_bp.route("/api/health/debug-raw")
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
