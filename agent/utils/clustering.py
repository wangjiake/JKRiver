
import hashlib
import json
import math
import random

from psycopg2.extras import RealDictCursor
from agent.storage import get_db_connection
from agent.utils.embedding import cosine_similarity
from agent.utils.llm_client import call_llm
from agent.config.prompts import get_prompt, get_labels


def _vec_add(a: list[float], b: list[float]) -> list[float]:
    return [x + y for x, y in zip(a, b)]


def _vec_scale(v: list[float], s: float) -> list[float]:
    return [x * s for x in v]


def _vec_norm(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def _normalize(v: list[float]) -> list[float]:
    n = _vec_norm(v)
    if n == 0:
        return v
    return [x / n for x in v]


def _cosine_distance(a: list[float], b: list[float]) -> float:
    return 1.0 - cosine_similarity(a, b)


def _kmeans_plusplus_init(vectors: list[list[float]], k: int) -> list[list[float]]:
    n = len(vectors)
    if k >= n:
        return [v[:] for v in vectors[:k]]

    first_idx = random.randint(0, n - 1)
    centroids = [vectors[first_idx][:]]

    for _ in range(1, k):
        distances = []
        for v in vectors:
            min_dist = min(_cosine_distance(v, c) for c in centroids)
            distances.append(min_dist * min_dist)
        total = sum(distances)
        if total == 0:
            idx = random.randint(0, n - 1)
        else:
            r = random.random() * total
            cumulative = 0.0
            idx = 0
            for i, d in enumerate(distances):
                cumulative += d
                if cumulative >= r:
                    idx = i
                    break
        centroids.append(vectors[idx][:])
    return centroids


def _kmeans(vectors: list[list[float]], k: int,
            max_iter: int = 15) -> tuple[list[int], list[list[float]]]:
    n = len(vectors)
    if n == 0:
        return [], []
    if k >= n:
        return list(range(n)), [v[:] for v in vectors]

    centroids = _kmeans_plusplus_init(vectors, k)
    assignments = [0] * n

    for _iteration in range(max_iter):
        changed = False
        # Assign each vector to nearest centroid
        for i, v in enumerate(vectors):
            best_cluster = 0
            best_dist = float('inf')
            for j, c in enumerate(centroids):
                d = _cosine_distance(v, c)
                if d < best_dist:
                    best_dist = d
                    best_cluster = j
            if assignments[i] != best_cluster:
                assignments[i] = best_cluster
                changed = True

        if not changed:
            break

        # Recompute centroids
        dims = len(vectors[0])
        new_centroids = [[0.0] * dims for _ in range(k)]
        counts = [0] * k
        for i, v in enumerate(vectors):
            c = assignments[i]
            new_centroids[c] = _vec_add(new_centroids[c], v)
            counts[c] += 1
        for j in range(k):
            if counts[j] > 0:
                new_centroids[j] = _normalize(_vec_scale(new_centroids[j], 1.0 / counts[j]))
            else:
                new_centroids[j] = centroids[j]
        centroids = new_centroids

    return assignments, centroids


def _determine_k(n: int) -> int:
    if n < 6:
        return max(1, n)
    return max(3, min(20, int(math.sqrt(n / 2))))


def _compute_embeddings_hash(rows: list[dict]) -> str:
    ids_str = ",".join(str(r["id"]) for r in sorted(rows, key=lambda r: r["id"]))
    return hashlib.sha256(ids_str.encode()).hexdigest()[:16]


def _load_all_embeddings() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, source_table, source_id, text_content, embedding "
                "FROM memory_embeddings ORDER BY id"
            )
            rows = []
            for r in cur.fetchall():
                emb = r["embedding"]
                if isinstance(emb, str):
                    emb = json.loads(emb)
                rows.append({
                    "id": r["id"],
                    "source_table": r["source_table"],
                    "source_id": r["source_id"],
                    "text_content": r["text_content"],
                    "embedding": emb,
                })
            return rows
    finally:
        conn.close()


def _get_last_embeddings_hash() -> str | None:
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT embeddings_hash FROM memory_clusters "
                    "ORDER BY id DESC LIMIT 1"
                )
                row = cur.fetchone()
                return row[0] if row else None
            except Exception:
                conn.rollback()
                return None
    finally:
        conn.close()


def _save_clusters(clusters_data: list[dict], embeddings_hash: str):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            try:
                cur.execute("DELETE FROM memory_clusters")
            except Exception:
                conn.rollback()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS memory_clusters ("
                    "  id SERIAL PRIMARY KEY,"
                    "  cluster_index INTEGER NOT NULL,"
                    "  theme TEXT,"
                    "  centroid JSONB NOT NULL,"
                    "  member_ids JSONB NOT NULL DEFAULT '[]',"
                    "  member_count INTEGER DEFAULT 0,"
                    "  representative_text TEXT,"
                    "  embeddings_hash VARCHAR(64),"
                    "  created_at TIMESTAMPTZ DEFAULT NOW(),"
                    "  updated_at TIMESTAMPTZ DEFAULT NOW()"
                    ")"
                )

            for cd in clusters_data:
                cur.execute(
                    "INSERT INTO memory_clusters "
                    "(cluster_index, theme, centroid, member_ids, member_count, "
                    " representative_text, embeddings_hash) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        cd["cluster_index"],
                        cd.get("theme", ""),
                        json.dumps(cd["centroid"]),
                        json.dumps(cd["member_ids"]),
                        cd["member_count"],
                        cd.get("representative_text", ""),
                        embeddings_hash,
                    ),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _generate_cluster_themes(clusters_info: list[dict], config: dict) -> list[dict]:
    llm_config = config.get("llm", {})
    language = config.get("language", "zh")
    prompt_text = get_prompt("sleep.cluster_themes", language)

    cluster_descriptions = []
    for ci in clusters_info:
        texts = ci["representative_texts"][:5]
        text_block = "\n".join(f"  - {t}" for t in texts)
        cluster_descriptions.append(
            f"Cluster {ci['cluster_index']} ({ci['member_count']} memories):\n{text_block}"
        )

    user_content = "\n\n".join(cluster_descriptions)

    messages = [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": user_content},
    ]

    raw = call_llm(messages, llm_config)
    try:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()
        themes = json.loads(raw)
        if isinstance(themes, list):
            return themes
    except Exception:
        pass
    return []


def cluster_memories(config: dict):
    emb_cfg = config.get("embedding", {})
    clustering_cfg = emb_cfg.get("clustering", {})
    if not clustering_cfg.get("enabled", False):
        return

    rows = _load_all_embeddings()
    if len(rows) < 6:
        return

    embeddings_hash = _compute_embeddings_hash(rows)
    last_hash = _get_last_embeddings_hash()
    if last_hash == embeddings_hash:
        return

    vectors = [r["embedding"] for r in rows]
    k = _determine_k(len(vectors))

    assignments, centroids = _kmeans(vectors, k)

    # Group members by cluster
    cluster_groups: dict[int, list[int]] = {}
    cluster_texts: dict[int, list[str]] = {}
    for i, cluster_idx in enumerate(assignments):
        cluster_groups.setdefault(cluster_idx, []).append(rows[i]["id"])
        cluster_texts.setdefault(cluster_idx, []).append(rows[i]["text_content"])

    # Build cluster info for theme generation
    clusters_info = []
    clusters_data = []
    for j in range(k):
        member_ids = cluster_groups.get(j, [])
        if not member_ids:
            continue
        texts = cluster_texts.get(j, [])
        rep_texts = texts[:5]

        clusters_info.append({
            "cluster_index": j,
            "member_count": len(member_ids),
            "representative_texts": rep_texts,
        })
        clusters_data.append({
            "cluster_index": j,
            "centroid": centroids[j] if j < len(centroids) else [],
            "member_ids": member_ids,
            "member_count": len(member_ids),
            "representative_text": rep_texts[0] if rep_texts else "",
            "theme": "",
        })

    # Generate themes with LLM (1 call)
    try:
        themes = _generate_cluster_themes(clusters_info, config)
        theme_map = {t["cluster_index"]: t.get("theme", "") for t in themes
                     if isinstance(t, dict)}
        for cd in clusters_data:
            cd["theme"] = theme_map.get(cd["cluster_index"], "")
    except Exception:
        pass

    _save_clusters(clusters_data, embeddings_hash)


def load_cluster_themes() -> list[dict]:
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                cur.execute(
                    "SELECT cluster_index, theme, member_count "
                    "FROM memory_clusters "
                    "WHERE theme IS NOT NULL AND theme != '' "
                    "ORDER BY member_count DESC"
                )
                return [dict(r) for r in cur.fetchall()]
            except Exception:
                conn.rollback()
                return []
    finally:
        conn.close()
