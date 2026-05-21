
import logging
from datetime import datetime, date
from decimal import Decimal
from flask import Blueprint, g, render_template, jsonify, request
from web._helpers import get_conn, _serialize, DB_NAME, load_config as _load_config
from agent.core.identity import DEFAULT_OWNER_ID

finance_bp = Blueprint("finance", __name__)


def _owner_id() -> int:
    return getattr(g, "owner_id", DEFAULT_OWNER_ID)


@finance_bp.route("/finance")
def finance_page():
    return render_template("finance.html", db_name=DB_NAME)


@finance_bp.route("/api/finance/overview")
def api_finance_overview():
    from agent.storage import get_finance_overview
    data = get_finance_overview(owner_id=_owner_id())
    return jsonify(data)


@finance_bp.route("/api/finance/transactions")
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
        owner_id=_owner_id(),
    )
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])


@finance_bp.route("/api/finance/summary")
def api_finance_summary():
    from agent.storage import get_finance_summary
    group_by = request.args.get("group_by", "month")
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    rows = get_finance_summary(group_by=group_by, year=year, month=month, owner_id=_owner_id())
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


@finance_bp.route("/api/finance/merchants")
def api_finance_merchants():
    from agent.storage import get_finance_merchant_stats
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    limit = request.args.get("limit", 20, type=int)
    rows = get_finance_merchant_stats(year=year, month=month, limit=limit, owner_id=_owner_id())
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])


@finance_bp.route("/api/finance/categories")
def api_finance_categories():
    from agent.storage import get_finance_category_stats
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    rows = get_finance_category_stats(year=year, month=month, owner_id=_owner_id())
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date, Decimal)) else v
                     for k, v in row.items()} for row in rows])


@finance_bp.route("/api/finance/import", methods=["POST"])
def api_finance_import():
    import re as _re
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


@finance_bp.route("/api/finance/transaction/<int:txn_id>", methods=["PUT"])
def api_finance_update_transaction(txn_id):
    from agent.storage import update_finance_transaction
    data = request.get_json(force=True)
    category = data.get("category")
    note = data.get("note")
    ok = update_finance_transaction(txn_id, category=category, note=note, owner_id=_owner_id())
    if ok:
        return jsonify({"ok": True, "id": txn_id})
    return jsonify({"error": "Record not found or no updates"}), 404


@finance_bp.route("/api/finance/merchant-categories")
def api_finance_merchant_categories_get():
    from agent.storage import load_merchant_categories
    rows = load_merchant_categories()
    return jsonify([{k: _serialize(v) if isinstance(v, (datetime, date)) else v
                     for k, v in row.items()} for row in rows])


@finance_bp.route("/api/finance/merchant-categories", methods=["POST"])
def api_finance_merchant_categories_post():
    from agent.storage import save_merchant_category
    data = request.get_json(force=True)
    pattern = data.get("merchant_pattern", "").strip()
    category = data.get("category", "").strip()
    if not pattern or not category:
        return jsonify({"error": "Parameters cannot be empty"}), 400
    mid = save_merchant_category(pattern, category)
    return jsonify({"ok": True, "id": mid})
