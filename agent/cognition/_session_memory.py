"""Session memory: sliding summary + vector recall + token budget."""

import asyncio
import logging
from datetime import datetime

from agent.config.prompts import get_labels, get_prompt
from agent.utils.time_context import get_now

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (overridden by config["session_memory"])
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "char_budget": 3000,
    "keep_recent": 5,
    "summary_ratio": 0.4,
    "recall_max": 3,
    "recall_min_score": 0.45,
}


class SessionMemory:
    """Three-layer session context: summary + recall + recent turns."""

    def __init__(self, config: dict, llm_config: dict, language: str,
                 session_id: str = ""):
        sm = config.get("session_memory", {})
        self.char_budget: int = sm.get("char_budget", _DEFAULTS["char_budget"])
        self.keep_recent: int = sm.get("keep_recent", _DEFAULTS["keep_recent"])
        self.summary_ratio: float = sm.get("summary_ratio", _DEFAULTS["summary_ratio"])
        self.recall_max: int = sm.get("recall_max", _DEFAULTS["recall_max"])
        self.recall_min_score: float = sm.get("recall_min_score", _DEFAULTS["recall_min_score"])

        self._llm_config = llm_config
        self._full_config = config
        self.language = language
        self.session_id = session_id

        # --- state ---
        self._turns: list[dict] = []        # all turns (user_summary, assistant_summary)
        self._summary: str = ""             # running summary covering old turns
        self._summary_covers: int = 0       # how many turns the summary covers

        # --- embedding index (in-memory) ---
        self._embeddings: list[dict] = []   # [{index, vec, user_input_at}]

    # ── public: add turns ──────────────────────────────────────

    def add_turn(self, user_summary: str, assistant_summary: str,
                 user_input_at: datetime | None = None):
        """Synchronous turn append (no compression)."""
        self._turns.append({
            "user_summary": user_summary,
            "assistant_summary": assistant_summary,
            "user_input_at": user_input_at or get_now(),
        })

    async def add_turn_async(self, user_summary: str, assistant_summary: str,
                             user_input_at: datetime | None = None):
        """Add turn + trigger compression + embed for recall."""
        ts = user_input_at or get_now()
        self._turns.append({
            "user_summary": user_summary,
            "assistant_summary": assistant_summary,
            "user_input_at": ts,
        })
        turn_index = len(self._turns) - 1

        # embed for recall (best-effort, run in thread to avoid blocking)
        await asyncio.to_thread(self._try_embed, turn_index, user_summary)

        # compress if needed
        await self._maybe_compress_async()

    # ── public: build context string ───────────────────────────

    def build_context(self, query_text: str = "") -> str:
        """Return formatted session context within char_budget."""
        if not self._turns:
            return ""

        L = get_labels("context.labels", self.language)

        # --- layer 3: recent N turns (always included, budget-free) ---
        recent = self._turns[-self.keep_recent:] if self.keep_recent else []
        recent_lines = []
        for t in recent:
            recent_lines.append(f"{L['user']}：{t['user_summary']}")
            recent_lines.append(f"{L['assistant']}：{t['assistant_summary']}")
        recent_text = "\n".join(recent_lines)

        remaining_budget = max(0, self.char_budget - len(recent_text))

        # --- layer 1: summary ---
        summary_budget = int(remaining_budget * self.summary_ratio)
        summary_text = ""
        if self._summary:
            session_summary_label = L.get("session_summary", "[Session Summary]")
            label_overhead = len(session_summary_label) + 1  # +1 for \n
            content_budget = max(0, summary_budget - label_overhead)
            truncated = self._summary[:content_budget]
            summary_text = f"{session_summary_label}\n{truncated}"

        # --- layer 2: recall ---
        recall_text = ""
        recall_budget = remaining_budget - len(summary_text)
        if query_text and recall_budget > 0:
            session_recalled_label = L.get("session_recalled", "[Recalled Context]")
            recall_label_overhead = len(session_recalled_label) + 1  # +1 for \n
            recall_content_budget = max(0, recall_budget - recall_label_overhead)
            if recall_content_budget > 0:
                recalled = self._recall_turns(query_text, recall_content_budget)
                if recalled:
                    recall_text = f"{session_recalled_label}\n{recalled}"

        # --- assemble ---
        parts = [p for p in [summary_text, recall_text] if p]
        if parts:
            prefix = "\n\n".join(parts)
            current_session_label = L.get("current_session", "Current Session")
            return f"{prefix}\n\n{current_session_label}：\n{recent_text}"
        else:
            current_session_label = L.get("current_session", "Current Session")
            return f"{current_session_label}：\n{recent_text}"

    # ── public: perceive-compatible (list[dict]) ───────────────

    def get_recent_turns(self, n: int = 3) -> list[dict]:
        """Return last n turns as list[dict] for perceive stage."""
        if not self._turns or n <= 0:
            return []
        return self._turns[-n:]

    # ── compression ────────────────────────────────────────────

    async def _maybe_compress_async(self):
        """Compress old turns into running summary when we have too many."""
        total = len(self._turns)
        if total <= self.keep_recent:
            return  # nothing to compress

        # Turns to compress: from summary_covers to (total - keep_recent)
        compress_end = total - self.keep_recent
        if compress_end <= self._summary_covers:
            return  # already compressed

        new_turns = self._turns[self._summary_covers:compress_end]
        if not new_turns:
            return

        # Build text for new turns
        turn_lines = []
        for t in new_turns:
            turn_lines.append(f"User: {t['user_summary']}")
            turn_lines.append(f"Assistant: {t['assistant_summary']}")
        new_turns_text = "\n".join(turn_lines)

        try:
            from agent.utils.llm_client import call_llm_async

            system_msg = get_prompt("session_memory.summarize_system", self.language)
            user_msg = get_prompt(
                "session_memory.summarize", self.language,
                existing_summary=self._summary or "(none)",
                new_turns=new_turns_text,
            )
            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ]
            result = await call_llm_async(messages, self._llm_config)
            result = result.strip()
            if result:
                self._summary = result
                self._summary_covers = compress_end
                logger.info("Session memory compressed %d turns (total covered: %d)",
                            len(new_turns), self._summary_covers)
        except Exception:
            # On failure, keep turns uncompressed; retry next time
            logger.warning("Session memory compression failed, will retry", exc_info=True)

    # ── vector recall ──────────────────────────────────────────

    def _try_embed(self, turn_index: int, text: str):
        """Best-effort embedding of a turn for later recall."""
        emb_cfg = self._full_config.get("embedding", {})
        if not emb_cfg.get("enabled", False):
            return
        try:
            from agent.utils.embedding import get_embedding
            model = emb_cfg.get("model", "")
            api_base = emb_cfg.get("api_base", "")
            vec = get_embedding(text, model=model, api_base=api_base)
            self._embeddings.append({
                "index": turn_index,
                "vec": vec,
                "user_input_at": self._turns[turn_index].get("user_input_at"),
            })
        except Exception:
            logger.debug("Session embedding failed for turn %d", turn_index, exc_info=True)

    def _recall_turns(self, query_text: str, budget: int) -> str:
        """Recall compressed turns by cosine similarity."""
        emb_cfg = self._full_config.get("embedding", {})
        if not emb_cfg.get("enabled", False):
            return ""
        if not self._embeddings:
            return ""

        # Only recall from compressed turns (index < total - keep_recent)
        compressed_boundary = max(0, len(self._turns) - self.keep_recent)
        candidates = [e for e in self._embeddings if e["index"] < compressed_boundary]
        if not candidates:
            return ""

        try:
            from agent.utils.embedding import get_embedding, cosine_similarity
            model = emb_cfg.get("model", "")
            api_base = emb_cfg.get("api_base", "")
            query_vec = get_embedding(query_text, model=model, api_base=api_base)

            scored = []
            for entry in candidates:
                score = cosine_similarity(query_vec, entry["vec"])
                if score >= self.recall_min_score:
                    scored.append((score, entry))

            scored.sort(key=lambda x: x[0], reverse=True)
            top = scored[:self.recall_max]

            if not top:
                return ""

            # Try to fetch full text from DB, fall back to in-memory summary
            lines = []
            for score, entry in top:
                full_text = self._fetch_full_turn(entry.get("user_input_at"))
                if full_text:
                    lines.append(full_text)
                else:
                    # Fallback: use in-memory summary
                    idx = entry["index"]
                    if idx < len(self._turns):
                        t = self._turns[idx]
                        lines.append(f"User: {t['user_summary']}\nAssistant: {t['assistant_summary']}")

                # Budget check
                if sum(len(l) for l in lines) >= budget:
                    break

            return "\n".join(lines)[:budget]
        except Exception:
            logger.debug("Session recall failed", exc_info=True)
            return ""

    def _fetch_full_turn(self, user_input_at: datetime | None) -> str | None:
        """Look up full conversation text from raw_conversations by session_id + timestamp."""
        if not self.session_id or not user_input_at:
            return None
        try:
            from agent.storage._db import get_db_connection
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_input, assistant_reply FROM raw_conversations "
                        "WHERE session_id = %s AND user_input_at = %s LIMIT 1",
                        (self.session_id, user_input_at),
                    )
                    row = cur.fetchone()
                    if row:
                        return f"User: {row[0]}\nAssistant: {row[1]}"
            finally:
                conn.close()
        except Exception:
            logger.debug("Failed to fetch full turn from DB", exc_info=True)
        return None
