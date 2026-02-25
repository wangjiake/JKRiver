
import hashlib
import math
import requests
from psycopg2.extras import RealDictCursor
from agent.storage import get_db_connection
from agent.config.prompts import get_labels

_table_ensured = False

def _ensure_embedding_table():
    global _table_ensured
    if _table_ensured:
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_embeddings (
                    id SERIAL PRIMARY KEY,
                    source_table VARCHAR(32) NOT NULL,
                    source_id INTEGER NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    text_content TEXT NOT NULL,
                    embedding JSONB NOT NULL,
                    model VARCHAR(64),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(source_table, source_id)
                );
            """)
        conn.commit()
        _table_ensured = True
    finally:
        conn.close()

def get_embedding(text: str, model: str = "",
                  api_base: str = "") -> list[float]:
    resp = requests.post(
        f"{api_base}/api/embed",
        json={"model": model, "input": text},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["embeddings"][0]

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

def vector_search(query_text: str, config: dict,
                  top_k: int = 5, min_score: float = 0.40) -> list[dict]:
    emb_cfg = config.get("embedding", {})
    model = emb_cfg.get("model", "")
    api_base = emb_cfg.get("api_base", "")
    search_cfg = emb_cfg.get("search", {})
    top_k = search_cfg.get("top_k", top_k)
    min_score = search_cfg.get("min_score", min_score)

    query_vec = get_embedding(query_text, model=model, api_base=api_base)

    _ensure_embedding_table()
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT source_table, source_id, text_content, embedding "
                "FROM memory_embeddings"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return []

    scored = []
    for row in rows:
        emb = row["embedding"]
        if isinstance(emb, str):
            import json
            emb = json.loads(emb)
        score = cosine_similarity(query_vec, emb)
        if score >= min_score:
            scored.append({
                "source_table": row["source_table"],
                "source_id": row["source_id"],
                "text_content": row["text_content"],
                "score": score,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]

def _profile_to_text(row: dict) -> str:
    return f"{row['category']} {row['subject']}: {row['value']}"

def _event_to_text(row: dict) -> str:
    return f"[{row.get('category', '')}] {row.get('summary', '')}"

def _observation_to_text(row: dict) -> str:
    subject = row.get("subject", "")
    content = row.get("content", "")
    if subject:
        L = get_labels("context.labels", "zh")
        return f"{content} ({L['topic_prefix']}: {subject})"
    return content

def _relationship_to_text(row: dict, language: str = "zh") -> str:
    import json as _json
    L = get_labels("context.labels", language)
    details = row.get("details", {})
    if isinstance(details, str):
        try:
            details = _json.loads(details)
        except Exception:
            details = {}
    detail_str = ", ".join(f"{k}: {v}" for k, v in details.items()) if details else ""
    name = row.get("name") or L.get("unknown_name", "(未知)")
    text = f"{row.get('relation', '')}: {name}"
    if detail_str:
        text += f" ({detail_str})"
    return text

def _conversation_to_text(row: dict) -> str:
    return row.get("ai_summary", "") or ""

_SOURCE_TABLES = [
    (
        "user_profile",
        "SELECT id, category, subject, value FROM user_profile WHERE end_time IS NULL AND rejected = false AND human_end_time IS NULL",
        _profile_to_text,
    ),
    (
        "event_log",
        "SELECT id, category, summary FROM event_log "
        "WHERE expires_at IS NULL OR expires_at > NOW()",
        _event_to_text,
    ),
    (
        "observations",
        "SELECT id, content, subject FROM observations WHERE rejected = false ORDER BY id DESC LIMIT 500",
        _observation_to_text,
    ),
    (
        "relationships",
        "SELECT id, relation, name, details FROM relationships WHERE status = 'active'",
        _relationship_to_text,
    ),
    (
        "conversation_turns",
        "SELECT id, ai_summary FROM conversation_turns "
        "WHERE ai_summary IS NOT NULL AND ai_summary != '' "
        "ORDER BY id DESC LIMIT 200",
        _conversation_to_text,
    ),
]

def embed_all_memories(config: dict):
    emb_cfg = config.get("embedding", {})
    if not emb_cfg.get("enabled", True):
        return

    model = emb_cfg.get("model", "")
    api_base = emb_cfg.get("api_base", "")

    try:
        get_embedding("test", model=model, api_base=api_base)
    except Exception as e:
        return

    _ensure_embedding_table()
    conn = get_db_connection()

    total_new = 0
    total_updated = 0
    total_skipped = 0

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT source_table, source_id, content_hash "
                "FROM memory_embeddings"
            )
            existing = {
                (r["source_table"], r["source_id"]): r["content_hash"]
                for r in cur.fetchall()
            }

        for table_name, query, to_text_fn in _SOURCE_TABLES:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(query)
                    rows = cur.fetchall()
            except Exception as e:
                conn.rollback()
                continue

            for row in rows:
                text = to_text_fn(row)
                if not text or not text.strip():
                    continue

                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                key = (table_name, row["id"])

                if key in existing and existing[key] == content_hash:
                    total_skipped += 1
                    continue

                try:
                    embedding = get_embedding(text, model=model, api_base=api_base)
                except Exception as e:
                    continue

                import json
                emb_json = json.dumps(embedding)

                with conn.cursor() as cur:
                    if key in existing:
                        cur.execute(
                            "UPDATE memory_embeddings "
                            "SET content_hash=%s, text_content=%s, embedding=%s, "
                            "    model=%s, updated_at=NOW() "
                            "WHERE source_table=%s AND source_id=%s",
                            (content_hash, text, emb_json, model,
                             table_name, row["id"]),
                        )
                        total_updated += 1
                    else:
                        cur.execute(
                            "INSERT INTO memory_embeddings "
                            "(source_table, source_id, content_hash, text_content, "
                            " embedding, model) "
                            "VALUES (%s, %s, %s, %s, %s, %s)",
                            (table_name, row["id"], content_hash, text,
                             emb_json, model),
                        )
                        total_new += 1

                conn.commit()

        _cleanup_orphaned(conn)

    finally:
        conn.close()

def _cleanup_orphaned(conn):
    cleanup_queries = {
        "user_profile": "DELETE FROM memory_embeddings WHERE source_table='user_profile' "
                        "AND source_id NOT IN (SELECT id FROM user_profile WHERE end_time IS NULL AND rejected = false AND human_end_time IS NULL)",
        "event_log": "DELETE FROM memory_embeddings WHERE source_table='event_log' "
                     "AND source_id NOT IN (SELECT id FROM event_log "
                     "WHERE expires_at IS NULL OR expires_at > NOW())",
        "relationships": "DELETE FROM memory_embeddings WHERE source_table='relationships' "
                         "AND source_id NOT IN (SELECT id FROM relationships WHERE status='active')",
    }
    total_cleaned = 0
    for table, query in cleanup_queries.items():
        try:
            with conn.cursor() as cur:
                cur.execute(query)
                total_cleaned += cur.rowcount
            conn.commit()
        except Exception:
            conn.rollback()

    if total_cleaned > 0:
        pass
