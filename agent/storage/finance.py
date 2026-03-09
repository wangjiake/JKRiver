import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from psycopg2.extras import RealDictCursor
from agent.utils.time_context import get_now
from ._db import get_db_connection

import psycopg2
from agent.config import load_config
from agent.config.prompts import get_labels

def _lang() -> str:
    return load_config().get("language", "en")

_finance_tables_ensured = False

def _ensure_finance_tables():
    global _finance_tables_ensured
    if _finance_tables_ensured:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS finance_transactions (
                    id SERIAL PRIMARY KEY,
                    transaction_date TIMESTAMPTZ NOT NULL,
                    merchant TEXT NOT NULL,
                    amount NUMERIC(12, 2) NOT NULL,
                    currency VARCHAR(8) NOT NULL DEFAULT 'JPY',
                    amount_jpy NUMERIC(12, 2),
                    category TEXT,
                    card_name TEXT DEFAULT 'credit_card',
                    email_id TEXT UNIQUE,
                    note TEXT,
                    metadata JSONB DEFAULT '{}',
                    imported_at TIMESTAMPTZ DEFAULT NOW(),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ft_date
                    ON finance_transactions(transaction_date DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ft_merchant
                    ON finance_transactions(merchant)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_ft_category
                    ON finance_transactions(category)
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS finance_merchant_categories (
                    id SERIAL PRIMARY KEY,
                    merchant_pattern TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            defaults = [
                ("イオン", "食品"), ("セリア", "日用品"),
                ("AMAZON", "网购"), ("CLAUDE.AI", "订阅"),
                ("OPENAI", "订阅"), ("NETFLIX", "订阅"),
                ("SPOTIFY", "订阅"), ("JR ", "交通"),
                ("SUICA", "交通"), ("スターバックス", "餐饮"),
                ("マクドナルド", "餐饮"), ("ユニクロ", "衣服"),
            ]
            for pattern, cat in defaults:
                cur.execute(
                    "INSERT INTO finance_merchant_categories (merchant_pattern, category) "
                    "VALUES (%s, %s) ON CONFLICT (merchant_pattern) DO NOTHING",
                    (pattern, cat),
                )
        conn.commit()
        _finance_tables_ensured = True
    finally:
        conn.close()

def parse_smcc_email(email_body: str) -> dict | None:
    if not email_body:
        return None

    date_match = re.search(r'◇利用日[：:\s]*(\d{4}/\d{1,2}/\d{1,2})', email_body)
    if not date_match:
        return None

    merchant_match = re.search(r'◇利用先[：:\s]*(.+?)[\r\n]', email_body)
    if not merchant_match:
        return None

    amount_match = re.search(
        r'◇利用金額[：:\s]*([\d,]+(?:\.\d+)?)\s*(円|JPY|USD|EUR|GBP|CNY)',
        email_body, re.IGNORECASE
    )
    if not amount_match:
        return None

    date_str = date_match.group(1)
    merchant = merchant_match.group(1).strip()
    amount_str = amount_match.group(1).replace(",", "")
    currency_raw = amount_match.group(2)

    currency = "JPY" if currency_raw in ("円", "JPY") else currency_raw.upper()

    try:
        txn_date = datetime.strptime(date_str, "%Y/%m/%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    try:
        amount = Decimal(amount_str)
    except Exception:
        return None

    return {
        "date": txn_date,
        "merchant": merchant,
        "amount": amount,
        "currency": currency,
    }

def _normalize_fullwidth(text: str) -> str:
    result = []
    for ch in text:
        cp = ord(ch)
        if 0xFF01 <= cp <= 0xFF5E:
            result.append(chr(cp - 0xFEE0))
        elif cp == 0x3000:
            result.append(' ')
        else:
            result.append(ch)
    return ''.join(result)

def _auto_categorize_merchant(merchant: str) -> str | None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT merchant_pattern, category "
                "FROM finance_merchant_categories ORDER BY id"
            )
            rows = cur.fetchall()
            merchant_normalized = _normalize_fullwidth(merchant).upper()
            for pattern, category in rows:
                if _normalize_fullwidth(pattern).upper() in merchant_normalized:
                    return category
            return None
    finally:
        conn.close()

def save_finance_transaction(
    transaction_date, merchant: str, amount,
    currency: str = "JPY", amount_jpy=None,
    category: str | None = None,
    card_name: str = "credit_card",
    email_id: str | None = None,
    note: str | None = None,
    metadata: dict | None = None,
) -> int | None:
    _ensure_finance_tables()
    if not category:
        category = _auto_categorize_merchant(merchant)
    if currency == "JPY" and amount_jpy is None:
        amount_jpy = amount

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "INSERT INTO finance_transactions "
                    "(transaction_date, merchant, amount, currency, amount_jpy, "
                    " category, card_name, email_id, note, metadata, "
                    " imported_at, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "RETURNING id",
                    (transaction_date, merchant, amount, currency, amount_jpy,
                     category, card_name, email_id, note,
                     json.dumps(metadata or {}, ensure_ascii=False),
                     get_now(), get_now()),
                )
                txn_id = cur.fetchone()[0]
                conn.commit()
                return txn_id
            except psycopg2.errors.UniqueViolation:
                conn.rollback()
                return None
    finally:
        conn.close()

def load_finance_transactions(
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    category: str | None = None,
    merchant: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)
    if day:
        conditions.append("EXTRACT(DAY FROM transaction_date) = %s")
        params.append(day)
    if category:
        conditions.append("category = %s")
        params.append(category)
    if merchant:
        conditions.append("merchant ILIKE %s")
        params.append(f"%{merchant}%")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.extend([limit, offset])

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT id, transaction_date, merchant, amount, currency, "
                f"amount_jpy, category, card_name, email_id, note, metadata, "
                f"imported_at, created_at "
                f"FROM finance_transactions {where} "
                f"ORDER BY transaction_date DESC "
                f"LIMIT %s OFFSET %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def update_finance_transaction(txn_id: int, category: str | None = None,
                                note: str | None = None) -> bool:
    _ensure_finance_tables()
    updates = []
    params: list = []
    if category is not None:
        updates.append("category = %s")
        params.append(category)
    if note is not None:
        updates.append("note = %s")
        params.append(note)
    if not updates:
        return False
    params.append(txn_id)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE finance_transactions SET {', '.join(updates)} "
                f"WHERE id = %s",
                params,
            )
            updated = cur.rowcount > 0
        conn.commit()
        return updated
    finally:
        conn.close()

def get_finance_summary(
    group_by: str = "month",
    year: int | None = None,
    month: int | None = None,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    if group_by == "year":
        group_expr = "EXTRACT(YEAR FROM transaction_date)"
        label_expr = "EXTRACT(YEAR FROM transaction_date)::int AS period"
        order = "period DESC"
    elif group_by == "day":
        group_expr = "transaction_date::date"
        label_expr = "transaction_date::date AS period"
        order = "period DESC"
    else:
        group_expr = "DATE_TRUNC('month', transaction_date)"
        label_expr = "TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') AS period"
        order = "period DESC"

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT {label_expr}, "
                f"COUNT(*) AS count, "
                f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy "
                f"FROM finance_transactions {where} "
                f"GROUP BY {group_expr} ORDER BY {order}",
                params,
            )
            summaries = list(cur.fetchall())

            for s in summaries:
                period_val = s["period"]
                if group_by == "year":
                    cat_cond = "EXTRACT(YEAR FROM transaction_date) = %s"
                    cat_params = [period_val]
                elif group_by == "day":
                    cat_cond = "transaction_date::date = %s"
                    cat_params = [period_val]
                else:
                    cat_cond = "TO_CHAR(DATE_TRUNC('month', transaction_date), 'YYYY-MM') = %s"
                    cat_params = [str(period_val)]

                _uncategorized = get_labels("context.labels", _lang()).get("uncategorized", "未分类")
                cur.execute(
                    f"SELECT COALESCE(category, %s) AS category, "
                    f"COUNT(*) AS count, "
                    f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy "
                    f"FROM finance_transactions "
                    f"WHERE {cat_cond} "
                    f"GROUP BY category ORDER BY total_jpy DESC",
                    [_uncategorized] + cat_params,
                )
                s["categories"] = list(cur.fetchall())

            return summaries
    finally:
        conn.close()

def get_finance_merchant_stats(
    year: int | None = None,
    month: int | None = None,
    limit: int = 20,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    params.append(limit)

    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT merchant, "
                f"COUNT(*) AS count, "
                f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy, "
                f"MAX(category) AS category "
                f"FROM finance_transactions {where} "
                f"GROUP BY merchant ORDER BY total_jpy DESC "
                f"LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_finance_category_stats(
    year: int | None = None,
    month: int | None = None,
) -> list[dict]:
    _ensure_finance_tables()
    conditions = []
    params: list = []

    if year:
        conditions.append("EXTRACT(YEAR FROM transaction_date) = %s")
        params.append(year)
    if month:
        conditions.append("EXTRACT(MONTH FROM transaction_date) = %s")
        params.append(month)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    conn = get_db_connection()
    try:
        _uncategorized = get_labels("context.labels", _lang()).get("uncategorized", "未分类")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                f"SELECT COALESCE(category, %s) AS category, "
                f"COUNT(*) AS count, "
                f"SUM(COALESCE(amount_jpy, amount)) AS total_jpy "
                f"FROM finance_transactions {where} "
                f"GROUP BY category ORDER BY total_jpy DESC",
                [_uncategorized] + params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()

def get_finance_overview() -> dict:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM finance_transactions")
            total_count = cur.fetchone()[0]
            cur.execute("SELECT COALESCE(SUM(COALESCE(amount_jpy, amount)), 0) FROM finance_transactions")
            total_amount = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT merchant) FROM finance_transactions")
            merchant_count = cur.fetchone()[0]
            cur.execute("SELECT MIN(transaction_date), MAX(transaction_date) FROM finance_transactions")
            row = cur.fetchone()
            date_from = row[0]
            date_to = row[1]
            return {
                "total_count": total_count,
                "total_amount": float(total_amount) if total_amount else 0,
                "merchant_count": merchant_count,
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
            }
    finally:
        conn.close()

def get_last_import_date() -> str | None:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(transaction_date) FROM finance_transactions"
            )
            row = cur.fetchone()
            if row and row[0]:
                d = row[0] - timedelta(days=3)
                return d.strftime("%Y/%m/%d")
            return None
    finally:
        conn.close()

def get_imported_email_ids() -> set[str]:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT email_id FROM finance_transactions "
                "WHERE email_id IS NOT NULL"
            )
            return {row[0] for row in cur.fetchall()}
    finally:
        conn.close()

def import_finance_from_email(email_id: str, email_subject: str,
                               email_body: str) -> dict:
    parsed = parse_smcc_email(email_body)
    if not parsed:
        return {"success": False, "duplicate": False, "parsed": None,
                "error": get_labels("context.labels", _lang())["parse_failed"]}

    txn_id = save_finance_transaction(
        transaction_date=parsed["date"],
        merchant=parsed["merchant"],
        amount=parsed["amount"],
        currency=parsed["currency"],
        email_id=email_id,
        metadata={"email_subject": email_subject},
    )

    if txn_id is None:
        return {"success": False, "duplicate": True, "parsed": parsed,
                "transaction_id": None}

    return {"success": True, "duplicate": False, "parsed": parsed,
            "transaction_id": txn_id}

def save_merchant_category(merchant_pattern: str, category: str) -> int:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO finance_merchant_categories (merchant_pattern, category) "
                "VALUES (%s, %s) "
                "ON CONFLICT (merchant_pattern) DO UPDATE SET category = EXCLUDED.category "
                "RETURNING id",
                (merchant_pattern, category),
            )
            mid = cur.fetchone()[0]
        conn.commit()
        return mid
    finally:
        conn.close()

def load_merchant_categories() -> list[dict]:
    _ensure_finance_tables()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, merchant_pattern, category, created_at "
                "FROM finance_merchant_categories ORDER BY id"
            )
            return list(cur.fetchall())
    finally:
        conn.close()
