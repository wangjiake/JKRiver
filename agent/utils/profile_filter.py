
import logging

from datetime import timedelta
from agent.utils.time_context import get_now
from agent.config.prompts import get_labels

logger = logging.getLogger(__name__)


def prepare_profile(profile, query_text=None, config=None,
                    max_entries=30, language="en"):
    """
    过滤 → 排序 → 截断

    1. 过滤：去掉 superseded_by is not None 的条目
    2. 排序：
       - 若 embedding 可用且 query_text 非空：用 vector_search 按相似度排序
       - 未匹配到的条目用 fallback 评分
       - 两组合并，去重，取前 max_entries
    3. rest_summary：剩余按 category 计数归并

    Returns: (top_entries: list[dict], rest_summary: str)
    """
    L = get_labels("context.labels", language)

    active = [p for p in profile if not p.get("superseded_by")]
    if not active:
        return [], ""

    vector_ranked_ids = []
    if query_text and config and config.get("embedding", {}).get("enabled"):
        try:
            from agent.utils.embedding import vector_search
            results = vector_search(
                query_text, config,
                source_tables=["user_profile"], top_k=max_entries,
            )
            vector_ranked_ids = [r["source_id"] for r in results]
        except Exception:
            logger.warning("vector search for profile failed", exc_info=True)

    id_to_entry = {p["id"]: p for p in active if p.get("id")}

    top = []
    seen_ids = set()

    for sid in vector_ranked_ids:
        entry = id_to_entry.get(sid)
        if entry and sid not in seen_ids:
            top.append(entry)
            seen_ids.add(sid)

    now = get_now()
    thirty_days_ago = now - timedelta(days=30)

    def _fallback_score(p):
        score = 0
        if p.get("layer") == "confirmed":
            score += 3
        updated = p.get("updated_at")
        if updated and updated >= thirty_days_ago:
            score += 2
        mc = p.get("mention_count") or 0
        if mc >= 3:
            score += 1
        return score

    remaining = [p for p in active if p.get("id") not in seen_ids]
    remaining.sort(key=_fallback_score, reverse=True)

    for p in remaining:
        if len(top) >= max_entries:
            break
        top.append(p)
        seen_ids.add(p.get("id"))

    rest = [p for p in active if p.get("id") not in seen_ids]
    rest_summary = ""
    if rest:
        from collections import Counter
        cat_counts = Counter(p.get("category", "?") for p in rest)
        parts = [f"{cat}×{cnt}" for cat, cnt in cat_counts.most_common()]
        rest_summary = L.get("rest_summary_prefix", "（其余") + " " + ", ".join(parts) + "）"

    return top, rest_summary


def format_profile_text(profile, keywords=None, config=None,
                        max_entries=30, detail="full", language="en"):
    """
    prepare_profile + 格式化为文本

    detail="full":  [核心] [职业] 当前公司: 字节跳动
    detail="light": [职业] 当前公司: 字节跳动

    Returns: str（top-K 完整行 + 摘要行）
    """
    L = get_labels("context.labels", language)
    top_entries, rest_summary = prepare_profile(
        profile, query_text=keywords, config=config,
        max_entries=max_entries, language=language,
    )
    if not top_entries:
        return ""

    lines = []
    for p in top_entries:
        if detail == "full":
            layer = p.get("layer", "suspected")
            if layer == "confirmed":
                tag = L["layer_core"]
            else:
                tag = L["layer_suspected"]
            lines.append(f"  {tag} [{p['category']}] {p['subject']}: {p['value']}")
        else:
            lines.append(f"  [{p['category']}] {p['subject']}: {p['value']}")

    text = "\n".join(lines)
    if rest_summary:
        text += "\n" + rest_summary
    return text
