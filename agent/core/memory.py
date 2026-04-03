import asyncio
import logging
from datetime import datetime, timezone

from agent.storage import (
    load_full_current_profile,
    load_pending_strategies,
    load_user_model,
    load_active_events,
    load_trajectory_summary,
    load_memory_snapshot,
    load_timeline,
    load_relationships,
    load_fact_edges,
)
from agent.utils.profile_filter import format_profile_text
from agent.config.prompts import get_labels

logger = logging.getLogger(__name__)


def _build_chat_memory_context(full_profile, user_model_data, perception,
                                config, language, L):
    """Build memory context for chat category (lightweight, early return)."""
    memory_parts = []
    query_text = perception.get("ai_summary", "")
    if full_profile:
        profile_text = format_profile_text(
            full_profile, keywords=query_text, config=config,
            max_entries=30, detail="full", language=language,
        )
        if profile_text:
            memory_parts.append(L["section_profile"] + "\n" + profile_text)
    if user_model_data:
        model_lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model_data]
        memory_parts.append(L["section_user_traits"] + "\n" + "\n".join(model_lines))
    memory_text = "\n\n".join(memory_parts) if memory_parts else ""
    profile_for_db = [
        {"category": p["category"], "field": p["subject"], "value": p["value"]}
        for p in full_profile
    ]
    return {
        "profile": profile_for_db,
        "hypotheses": full_profile,
        "strategies": [],
        "user_model": user_model_data,
        "events": [],
        "strategy_ids": [],
        "memory_text": memory_text,
    }


def _load_fact_edges_safe(full_profile):
    """Load fact edges, return [] on error with warning."""
    if not full_profile:
        return []
    try:
        profile_ids = [p["id"] for p in full_profile if p.get("id")]
        return load_fact_edges(profile_ids) or []
    except Exception:
        logger.warning("fact_edges load failed", exc_info=True)
        return []


def _load_vector_results_safe(perception, config):
    """Vector search, return [] on error with warning."""
    if not (config and config.get("embedding", {}).get("enabled")):
        return []
    try:
        from agent.utils.embedding import vector_search
        query_parts = []
        ai_summary = perception.get("ai_summary", "")
        if ai_summary:
            query_parts.append(ai_summary)
        for kw in perception.get("topic_keywords", []):
            query_parts.append(kw)
        query_text = " ".join(query_parts)
        if not query_text.strip():
            return []
        return vector_search(query_text, config) or []
    except Exception:
        logger.warning("vector search failed", exc_info=True)
        return []


def _load_cluster_themes_safe(config):
    """Load cluster themes, return [] on error with warning."""
    if not (config and config.get("embedding", {}).get("clustering", {}).get("show_themes")):
        return []
    try:
        from agent.utils.clustering import load_cluster_themes
        return load_cluster_themes() or []
    except Exception:
        logger.warning("cluster themes load failed", exc_info=True)
        return []


def _assemble_memory_context(
    *,
    perception: dict,
    full_profile: list,
    user_model_data: list,
    config: dict | None,
    language: str,
    L: dict,
    executed_strategy_ids: set,
    all_strategies: list,
    relationships_data: list | None,
    events: list,
    trajectory_data: dict | None,
    snapshot: dict | None,
    timeline: list,
    fact_edges: list,
    vs_results: list,
    cluster_themes: list,
) -> dict:
    """Assemble memory context dict from pre-loaded data."""
    import json
    strategies = [s for s in all_strategies if s["id"] not in executed_strategy_ids]
    strategy_ids_in_context = [s["id"] for s in strategies[:2]]

    memory_parts = []
    query_text = perception.get("ai_summary", "")

    # Profile / snapshot
    if snapshot and snapshot.get("snapshot_text"):
        memory_parts.append(L["section_profile"] + "\n" + snapshot["snapshot_text"])
    else:
        profile_text = format_profile_text(
            full_profile, keywords=query_text, config=config,
            max_entries=30, detail="full", language=language,
        )
        if profile_text:
            memory_parts.append(L["section_profile"] + "\n" + profile_text)

    # Timeline
    changed_keys = set()
    for t in timeline:
        if t["end_time"] is not None or t.get("human_end_time") is not None or t.get("rejected"):
            changed_keys.add((t["category"], t["subject"]))
    if changed_keys:
        timeline_lines = []
        for cat, subj in sorted(changed_keys):
            entries = sorted(
                [t for t in timeline if t["category"] == cat and t["subject"] == subj],
                key=lambda x: x["start_time"] or datetime.min.replace(tzinfo=timezone.utc),
            )
            for t in entries:
                start_str = t["start_time"].strftime("%Y-%m") if t["start_time"] else "?"
                eff_end = t.get("human_end_time") or t.get("end_time")
                if t.get("rejected"):
                    timeline_lines.append(
                        f"  [{cat}] {subj}: {t['value']} ({start_str}, {L['marked_error']})")
                elif eff_end:
                    end_str = eff_end.strftime("%Y-%m")
                    timeline_lines.append(
                        f"  [{cat}] {subj}: {t['value']} ({start_str} ~ {end_str}, {L['ended']})")
                else:
                    timeline_lines.append(
                        f"  [{cat}] {subj}: {t['value']} ({start_str} ~ {L['until_now']}, {L['current_tag']})")
        memory_parts.append(L["section_timeline"] + "\n" + "\n".join(timeline_lines))

    # Strategies
    if strategies[:2]:
        strat_lines = []
        for s in strategies[:2]:
            strat_lines.append(
                f"  [{s['strategy_type']}] {s['description']}\n"
                f"    {L['trigger_condition_label']}: {s['trigger_condition']}\n"
                f"    {L['approach_label']}: {s['approach']}"
            )
        memory_parts.append(
            L["section_strategies"] + "\n" + "\n".join(strat_lines)
        )

    # Relationships
    if relationships_data:
        relationships_data = sorted(
            relationships_data,
            key=lambda r: r.get("mention_count", 0),
            reverse=True,
        )[:10]
        rel_lines = []
        for r in relationships_data:
            details = r.get("details", {})
            if isinstance(details, str):
                details = json.loads(details) if details else {}
            detail_str = "，".join(f"{k}: {v}" for k, v in details.items()) if details else ""
            name_str = r.get("name") or L["unknown_name"]
            line = f"  {r['relation']}: {name_str}"
            if detail_str:
                line += f"（{detail_str}）"
            rel_lines.append(line)
        memory_parts.append(L["section_relationships"] + "\n" + "\n".join(rel_lines))

    # User model
    if user_model_data:
        model_lines = [f"  {m['dimension']}: {m['assessment']}" for m in user_model_data]
        memory_parts.append(L["section_user_traits"] + "\n" + "\n".join(model_lines))

    # Events
    if events:
        event_lines = [f"  [{e['category']}] {e['summary']}" for e in events]
        memory_parts.append(L["section_events"] + "\n" + "\n".join(event_lines))

    # Trajectory
    if trajectory_data and trajectory_data.get("life_phase"):
        traj_lines = [
            f"  {L['phase']}: {trajectory_data.get('life_phase', '?')}",
            f"  {L['direction']}: {trajectory_data.get('trajectory_direction', '?')}",
            f"  {L['stability']}: {trajectory_data.get('stability_assessment', '?')}",
            f"  {L['anchors']}: {json.dumps(trajectory_data.get('key_anchors', []), ensure_ascii=False)}",
            f"  {L['volatile_areas']}: {json.dumps(trajectory_data.get('volatile_areas', []), ensure_ascii=False)}",
        ]
        if trajectory_data.get('recent_momentum'):
            traj_lines.append(f"  {L['momentum']}: {trajectory_data['recent_momentum']}")
        memory_parts.append(L["section_trajectory"] + "\n" + "\n".join(traj_lines))

    # Fact edges (knowledge network)
    if fact_edges:
        edge_lines = [
            f"  [{e.get('src_category','')}/{e.get('src_subject','')}] "
            f"--[{e['edge_type']}]--> "
            f"[{e.get('tgt_category','')}/{e.get('tgt_subject','')}]: "
            f"{e.get('description', '')}"
            for e in fact_edges[:15]
        ]
        memory_parts.append(L["section_knowledge_network"] + "\n" + "\n".join(edge_lines))

    # Vector search results (deduplicated)
    if vs_results:
        existing_profile_ids = {p.get("id") for p in full_profile if p.get("id")}
        existing_event_ids = {e.get("id") for e in events if e.get("id")}
        unique_results = []
        for r in vs_results:
            if r["source_table"] == "user_profile" and r["source_id"] in existing_profile_ids:
                continue
            if r["source_table"] == "event_log" and r["source_id"] in existing_event_ids:
                continue
            unique_results.append(r)
        if unique_results:
            vs_lines = [
                f"  [{r['source_table']}] {r['text_content']} ({L['relevance']}: {r['score']:.2f})"
                for r in unique_results
            ]
            memory_parts.append(L["section_vector_search"] + "\n" + "\n".join(vs_lines))

    # Cluster themes
    if cluster_themes:
        theme_lines = [
            f"  [{t['member_count']} memories] {t['theme']}"
            for t in cluster_themes
        ]
        memory_parts.append(L["section_cluster_themes"] + "\n" + "\n".join(theme_lines))

    memory_text = "\n\n".join(memory_parts) if memory_parts else ""

    profile_for_db = [
        {"category": p["category"], "field": p["subject"], "value": p["value"]}
        for p in full_profile
    ]

    return {
        "profile": profile_for_db,
        "hypotheses": full_profile,
        "strategies": strategies[:2],
        "user_model": user_model_data,
        "events": events,
        "strategy_ids": strategy_ids_in_context,
        "memory_text": memory_text,
    }


async def build_memory_context_async(perception: dict,
                                     executed_strategy_ids: set | None = None,
                                     config: dict | None = None) -> dict:
    """Build memory context — parallelizes independent DB queries."""
    if executed_strategy_ids is None:
        executed_strategy_ids = set()

    language = config.get("language", "en") if config else "en"
    L = get_labels("context.labels", language)
    category = perception.get("category", "chat")

    if category == "chat":
        full_profile, user_model_data = await asyncio.gather(
            asyncio.to_thread(load_full_current_profile),
            asyncio.to_thread(load_user_model),
        )
        return _build_chat_memory_context(full_profile, user_model_data,
                                          perception, config, language, L)

    # Round 1: all independent DB queries in parallel
    topic_keywords = perception.get("topic_keywords", [])
    (full_profile, user_model_data, all_strategies,
     relationships_data, events, trajectory_data,
     snapshot, timeline) = await asyncio.gather(
        asyncio.to_thread(load_full_current_profile),
        asyncio.to_thread(load_user_model),
        asyncio.to_thread(load_pending_strategies,
                          topic_keywords if topic_keywords else None),
        asyncio.to_thread(load_relationships),
        asyncio.to_thread(load_active_events, 5),
        asyncio.to_thread(load_trajectory_summary),
        asyncio.to_thread(load_memory_snapshot),
        asyncio.to_thread(load_timeline),
    )

    # Round 2: queries that may depend on profile
    fact_edges, vs_results, cluster_themes = await asyncio.gather(
        asyncio.to_thread(_load_fact_edges_safe, full_profile),
        asyncio.to_thread(_load_vector_results_safe, perception, config),
        asyncio.to_thread(_load_cluster_themes_safe, config),
    )

    return _assemble_memory_context(
        perception=perception,
        full_profile=full_profile,
        user_model_data=user_model_data,
        config=config,
        language=language,
        L=L,
        executed_strategy_ids=executed_strategy_ids,
        all_strategies=all_strategies,
        relationships_data=relationships_data,
        events=events,
        trajectory_data=trajectory_data,
        snapshot=snapshot,
        timeline=timeline,
        fact_edges=fact_edges,
        vs_results=vs_results,
        cluster_themes=cluster_themes,
    )
