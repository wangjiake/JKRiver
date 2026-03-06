import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from agent.cognition import CognitionEngine
from agent.utils.time_context import get_now
from agent.storage import (
    save_raw_conversation, save_conversation_turn,
    load_full_current_profile, load_timeline,
    load_pending_strategies, mark_strategy_executed,
    load_user_model, load_active_events,
    load_trajectory_summary,
    load_relationships,
    load_memory_snapshot,
    load_fact_edges,
)
from agent.utils.profile_filter import format_profile_text
from agent.tools import ToolRegistry
from agent.tools.preprocess import preprocess_input
from agent.tools._resolver import resolve_tools, resolve_tools_async
import asyncio
from agent.config.prompts import get_labels
from agent.skills import SkillRegistry
from agent.skills.creator import detect_skill_request, create_skill_from_chat, delete_skill, extract_skill_name
from agent.skills.executor import execute_skill

logger = logging.getLogger(__name__)

class Session:
    def __init__(self, config: dict, session_id: str | None = None):
        self.id = session_id or str(uuid.uuid4())
        self.created_at = get_now()
        self.full_config = config
        self.cognition = CognitionEngine(config)
        self.executed_strategy_ids: set = set()
        tools_enabled = config.get("tools", {}).get("enabled", True)
        self.tool_registry = ToolRegistry(config) if tools_enabled else ToolRegistry.__new__(ToolRegistry)
        if not tools_enabled:
            self.tool_registry.config = config
            self.tool_registry._tools = {}
        self.skill_registry = SkillRegistry(config)

class SessionManager:
    def __init__(self, config: dict):
        self.config = config
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None = None) -> Session:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        session = Session(self.config, session_id)
        self._sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str):
        self._sessions.pop(session_id, None)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())


# ── build_memory_context helpers ──────────────────────────

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
    """Assemble memory context dict from pre-loaded data. Shared by sync/async."""
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


# ── build_memory_context (sync / async) ──────────────────

def build_memory_context(perception: dict,
                         executed_strategy_ids: set | None = None,
                         config: dict | None = None) -> dict:
    if executed_strategy_ids is None:
        executed_strategy_ids = set()

    language = config.get("language", "zh") if config else "zh"
    L = get_labels("context.labels", language)

    full_profile = load_full_current_profile()
    user_model_data = load_user_model()

    if perception.get("category", "chat") == "chat":
        return _build_chat_memory_context(full_profile, user_model_data,
                                          perception, config, language, L)

    topic_keywords = perception.get("topic_keywords", [])
    all_strategies = load_pending_strategies(
        topic_keywords=topic_keywords if topic_keywords else None)
    relationships_data = load_relationships()
    events = load_active_events(top_k=5)
    trajectory_data = load_trajectory_summary()
    snapshot = load_memory_snapshot()
    timeline = load_timeline()

    fact_edges = _load_fact_edges_safe(full_profile)
    vs_results = _load_vector_results_safe(perception, config)
    cluster_themes = _load_cluster_themes_safe(config)

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


async def build_memory_context_async(perception: dict,
                                     executed_strategy_ids: set | None = None,
                                     config: dict | None = None) -> dict:
    """Async version — parallelizes independent DB queries."""
    if executed_strategy_ids is None:
        executed_strategy_ids = set()

    language = config.get("language", "zh") if config else "zh"
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


def _build_trajectory_block(trajectory: dict, L: dict) -> str:
    """Build trajectory divergence block for memory context."""
    block = L["section_trajectory_divergence"] + "\n"
    block += f"  {L['judgment']}: {trajectory.get('trajectory', '?')} — {trajectory.get('reasoning', '')}\n"
    causes = trajectory.get("possible_causes", [])
    if causes:
        block += f"  {L['possible_causes_label']}: {', '.join(causes)}\n"
    if trajectory.get("real_need"):
        block += f"  {L['real_need_guess']}: {trajectory['real_need']}\n"
    block += f"  {L['immediate_strategy_text']}\n"
    is_temp = trajectory.get("is_temporary", True)
    block += f"  {L['persistence_label']}: {L['persistence_temp'] if is_temp else L['persistence_lasting']}"
    return block


def _inject_tool_context(tool_results: list[dict], memories: dict, llm_input: str,
                         L: dict, log_fn) -> str:
    """Inject tool results into memory context, handle image placeholders. Returns updated llm_input."""
    if not tool_results:
        return llm_input
    _tool_labels = {
        "image_describe": L["tool_label_image"],
        "web_search": L["tool_label_web_search"],
        "voice_transcribe": L["tool_label_voice"],
        "finance_query": L["tool_label_finance"],
        "health_query": L["tool_label_health"],
    }
    tool_context = "\n\n".join(
        f"【{_tool_labels.get(t['tool'], t['tool'])}】\n{t['result'].data}"
        for t in tool_results if t["result"].success
    )
    if tool_context:
        if memories["memory_text"]:
            memories["memory_text"] += "\n\n" + tool_context
        else:
            memories["memory_text"] = tool_context
        if log_fn:
            log_fn("info", f"工具结果已注入上下文 ({len(tool_results)} 个工具)")

    for t in tool_results:
        if t["tool"] == "image_describe" and t["result"].success:
            placeholder = L["image_placeholder"]
            clean_input = llm_input.replace(placeholder + " ", "").replace(placeholder, "").strip()
            llm_input = L["image_recognized_prefix"] + clean_input
    return llm_input


def _handle_skills(processed_text: str, session, memories: dict, L: dict, log_fn):
    """Handle skill creation, deletion, and matching."""
    language = session.full_config.get("language", "zh")
    if not session.full_config.get("skills", {}).get("enabled", True):
        return

    skill_action = detect_skill_request(processed_text, language=language)
    if skill_action == "create":
        result = create_skill_from_chat(
            processed_text, session.cognition.config,
            session.tool_registry.list_available(),
            language=language,
        )
        if result["success"]:
            session.skill_registry.reload()
            inject = (f"\n\n{L['skill_created_header']}\n{L['skill_name_label']}: {result['skill_name']}\n"
                      f"{L['skill_desc_label']}: {result['description']}\n{result['message']}")
        else:
            inject = f"\n\n{L['skill_create_failed_header']}\n{result['message']}"
        memories["memory_text"] += inject
        if log_fn:
            log_fn("info", f"技能创建: {result}")
    elif skill_action == "delete":
        skill_name = extract_skill_name(processed_text, language=language)
        if skill_name:
            deleted = delete_skill(skill_name)
            if deleted:
                session.skill_registry.reload()
                inject = f"\n\n{L['skill_deleted_header']}\n{L['skill_deleted_label']}: {skill_name}"
            else:
                inject = f"\n\n{L['skill_delete_failed_header']}\n{L['skill_not_found']}: {skill_name}"
        else:
            inject = f"\n\n{L['skill_delete_failed_header']}\n{L['skill_delete_no_name']}"
        memories["memory_text"] += inject
        if log_fn:
            log_fn("info", f"技能删除: skill_name={skill_name}")

    matched_skills = session.skill_registry.match_keywords(processed_text)
    for skill in matched_skills:
        try:
            if skill.is_simple:
                inject = f"\n\n{L['skill_guide_header'].format(description=skill.description)}\n{skill.instruction}"
            else:
                result = execute_skill(
                    skill, session.tool_registry,
                    session.cognition.config, session.full_config,
                )
                inject = f"\n\n【{skill.description}】\n{result}"
            memories["memory_text"] += inject
            if log_fn:
                log_fn("info", f"技能匹配: {skill.name}")
        except Exception as e:
            if log_fn:
                log_fn("info", f"技能执行失败 {skill.name}: {e}")


def _save_turn_data(session, perception: dict, think_result: dict,
                    memories: dict, memories_used_at, user_input_at,
                    raw_user_input: str, final_response: str,
                    tool_results: list[dict], input_metadata: dict, L: dict):
    """Save raw conversation + detailed conversation turn to DB."""
    assistant_reply_at = get_now()

    for s in memories.get("strategies", []):
        mark_strategy_executed(s["id"], result=L["strategy_executed_result"])

    save_raw_conversation(
        session_id=session.id,
        session_created_at=session.created_at,
        user_input=raw_user_input,
        user_input_at=user_input_at,
        assistant_reply=final_response,
        assistant_reply_at=assistant_reply_at,
    )

    completed_at = get_now()
    memories_for_db = []
    if memories["profile"]:
        memories_for_db.append({
            "type": "profile",
            "data": [{"category": p["category"], "field": p["field"],
                       "value": p["value"]} for p in memories["profile"]],
        })
    if memories["hypotheses"]:
        memories_for_db.append({
            "type": "profile",
            "data": [{"category": h["category"], "subject": h["subject"],
                       "value": h.get("value") or h.get("claim", ""),
                       "layer": h.get("layer", "suspected")}
                      for h in memories["hypotheses"]],
        })
    if memories["events"]:
        memories_for_db.append({
            "type": "events",
            "data": [{"category": e["category"], "summary": e["summary"]}
                      for e in memories["events"]],
        })

    file_data = None
    file_path = input_metadata.get("file_path", "")
    if file_path and input_metadata.get("type") in ("image", "voice", "file"):
        try:
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    file_data = f.read()
        except Exception:
            pass

    save_conversation_turn({
        "session_id": session.id,
        "session_created_at": session.created_at,
        "user_input": raw_user_input,
        "user_input_at": user_input_at,
        "assistant_reply": final_response,
        "assistant_reply_at": assistant_reply_at,
        "intent": perception["intent"],
        "need_memory": perception["need_memory"],
        "memory_type": perception["memory_type"],
        "ai_summary": perception["ai_summary"],
        "perception_at": perception["perception_at"],
        "memories_used": memories_for_db,
        "memories_used_at": memories_used_at,
        "raw_response": think_result["raw_response"],
        "raw_response_at": think_result["raw_response_at"],
        "verification_result": think_result["verification_result"],
        "verification_result_at": think_result["verification_result_at"],
        "final_response": think_result["final_response"],
        "final_response_at": think_result["final_response_at"],
        "thinking_notes": think_result["thinking_notes"],
        "thinking_notes_at": think_result["thinking_notes_at"],
        "completed_at": completed_at,
        "input_type": input_metadata.get("type", "text"),
        "file_path": file_path,
        "file_data": file_data,
        "tool_results": [
            {"tool": t["tool"], "params": t["params"],
             "success": t["result"].success,
             "data": t["result"].data[:500] if t["result"].success else "",
             "error": t["result"].error}
            for t in tool_results
        ] if tool_results else [],
    })


def _extract_citations(tool_results: list[dict], language: str = "zh") -> str:
    L = get_labels("context.labels", language)
    citation_label = L.get("citation_header", L.get("citation_header_default", "Sources"))
    seen = set()
    lines = []
    for t in tool_results:
        if not t["result"].success:
            continue
        data = t["result"].data
        pattern = re.escape(citation_label) + r":\n(.+)"
        ref_match = re.search(pattern, data, re.DOTALL)
        if ref_match:
            for line in ref_match.group(1).strip().split("\n"):
                line = line.strip()
                if line and line not in seen:
                    seen.add(line)
                    lines.append(line)
        else:
            for m in re.finditer(r"\[([^\]]+)\]\((https?://[^\)]+)\)", data):
                title, url = m.group(1), m.group(2)
                clean_url = re.sub(r"[?&]utm_source=openai", "", url)
                entry = f"- {title}: {clean_url}"
                if entry not in seen:
                    seen.add(entry)
                    lines.append(entry)
    if lines:
        return f"{citation_label}:\n" + "\n".join(lines)
    return ""


def _finalize_response(think_result: dict, tool_results: list[dict],
                        language: str) -> str:
    """Append citations to final_response if tool results contain references."""
    final_response = think_result["final_response"]
    if tool_results:
        citations = _extract_citations(tool_results, language=language)
        if citations:
            final_response += "\n\n" + citations
            think_result["final_response"] = final_response
    return final_response


def run_cycle(user_input: str | dict, session: Session,
              log_fn=None) -> dict:
    def log(level, msg):
        if log_fn:
            log_fn(level, msg)

    user_input_at = get_now()

    if isinstance(user_input, str):
        raw_input = {"type": "text", "text": user_input}
    else:
        raw_input = user_input

    language = session.full_config.get("language", "zh")
    L = get_labels("context.labels", language)

    processed_text, input_metadata = preprocess_input(raw_input, session.tool_registry, language=language)
    log("info", f"输入类型={input_metadata['type']} 处理后={processed_text[:80]}")

    raw_user_input = raw_input.get("text", "") or processed_text

    log("info", "感知中...")
    perception = session.cognition.perceive(
        processed_text,
        available_tools=session.tool_registry.list_available(),
    )
    category = perception.get("category", "chat")
    log("info", f"分类={category} 意图={perception['intent']}")

    corrected_input = perception.get("corrected_input", processed_text)
    if corrected_input != processed_text:
        llm_input = f"{corrected_input}\n{L['original_input_suffix'].format(text=processed_text)}"
    else:
        llm_input = processed_text

    trajectory = None
    if category == "knowledge":
        memories = {
            "profile": [], "hypotheses": [], "strategies": [],
            "user_model": [], "events": [], "strategy_ids": [],
            "memory_text": "",
        }
        memories_used_at = get_now()
    else:
        memories = build_memory_context(perception, session.executed_strategy_ids,
                                        config=session.full_config)
        session.executed_strategy_ids.update(memories.get("strategy_ids", []))
        memories_used_at = get_now()

        if category == "personal":
            trajectory = session.cognition.analyze_trajectory(llm_input, memories)
            if trajectory:
                trajectory_block = _build_trajectory_block(trajectory, L)
                if memories["memory_text"]:
                    memories["memory_text"] += "\n\n" + trajectory_block
                else:
                    memories["memory_text"] = trajectory_block

    tool_results = resolve_tools(
        processed_text, perception, session.tool_registry,
        session.cognition.config, input_metadata,
        language=language,
        profile=memories.get("profile"),
    )

    llm_input = _inject_tool_context(tool_results, memories, llm_input, L, log_fn)
    _handle_skills(processed_text, session, memories, L, log_fn)

    has_tool_data = any(t["result"].success and t["result"].data for t in tool_results) if tool_results else False
    log("info", f"思考中...{'(云端)' if has_tool_data else '(本地)'}")
    think_result = session.cognition.think(llm_input, perception, memories, use_cloud=has_tool_data)
    final_response = _finalize_response(think_result, tool_results, language)

    _save_turn_data(session, perception, think_result, memories, memories_used_at,
                    user_input_at, raw_user_input, final_response, tool_results, input_metadata, L)

    return {
        "response": final_response,
        "perception": perception,
        "memories": memories,
        "trajectory": trajectory,
        "think_result": think_result,
    }

# ── Async version with parallel execution ──

async def run_cycle_async(user_input: str | dict, session: Session,
                          log_fn=None) -> dict:
    def log(level, msg):
        if log_fn:
            log_fn(level, msg)

    user_input_at = get_now()

    if isinstance(user_input, str):
        raw_input = {"type": "text", "text": user_input}
    else:
        raw_input = user_input

    language = session.full_config.get("language", "zh")
    L = get_labels("context.labels", language)

    processed_text, input_metadata = preprocess_input(raw_input, session.tool_registry, language=language)
    log("info", f"输入类型={input_metadata['type']} 处理后={processed_text[:80]}")

    raw_user_input = raw_input.get("text", "") or processed_text

    log("info", "感知中...")
    perception = await session.cognition.perceive_async(
        processed_text,
        available_tools=session.tool_registry.list_available(),
    )
    category = perception.get("category", "chat")
    log("info", f"分类={category} 意图={perception['intent']}")

    corrected_input = perception.get("corrected_input", processed_text)
    if corrected_input != processed_text:
        llm_input = f"{corrected_input}\n{L['original_input_suffix'].format(text=processed_text)}"
    else:
        llm_input = processed_text

    trajectory = None
    if category == "knowledge":
        memories = {
            "profile": [], "hypotheses": [], "strategies": [],
            "user_model": [], "events": [], "strategy_ids": [],
            "memory_text": "",
        }
        memories_used_at = get_now()
        tool_results = await resolve_tools_async(
            processed_text, perception, session.tool_registry,
            session.cognition.config, input_metadata,
            language=language,
        )
    else:
        # Memory build + tool resolution in parallel
        log("info", "记忆构建 + 工具调度 并行中...")

        memories, tool_results = await asyncio.gather(
            build_memory_context_async(perception, session.executed_strategy_ids,
                                       config=session.full_config),
            resolve_tools_async(
                processed_text, perception, session.tool_registry,
                session.cognition.config, input_metadata,
                language=language,
            ),
        )

        session.executed_strategy_ids.update(memories.get("strategy_ids", []))
        memories_used_at = get_now()

        if category == "personal":
            trajectory = await session.cognition.analyze_trajectory_async(llm_input, memories)
            if trajectory:
                trajectory_block = _build_trajectory_block(trajectory, L)
                if memories["memory_text"]:
                    memories["memory_text"] += "\n\n" + trajectory_block
                else:
                    memories["memory_text"] = trajectory_block

    llm_input = _inject_tool_context(tool_results, memories, llm_input, L, log_fn)
    _handle_skills(processed_text, session, memories, L, log_fn)

    has_tool_data = any(t["result"].success and t["result"].data for t in tool_results) if tool_results else False
    log("info", f"思考中...{'(云端)' if has_tool_data else '(本地)'}")
    think_result = await session.cognition.think_async(llm_input, perception, memories, use_cloud=has_tool_data)
    final_response = _finalize_response(think_result, tool_results, language)

    _save_turn_data(session, perception, think_result, memories, memories_used_at,
                    user_input_at, raw_user_input, final_response, tool_results, input_metadata, L)

    return {
        "response": final_response,
        "perception": perception,
        "memories": memories,
        "trajectory": trajectory,
        "think_result": think_result,
    }
