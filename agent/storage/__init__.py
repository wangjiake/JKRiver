"""
agent.storage — re-exports from domain sub-modules.

All public API is importable directly from `agent.storage`.
"""

# ── database ──
from ._db import get_db_connection, DB_CONFIG, transaction  # noqa: F401

# ── conversation ──
from .conversation import (  # noqa: F401
    save_raw_conversation,
    save_conversation_turn,
    save_session_tag,
    load_existing_tags,
    save_session_summary,
    search_sessions_by_tag,
)

# ── events ──
from .events import (  # noqa: F401
    save_event,
    load_active_events,
)

# ── observations ──
from .observations import (  # noqa: F401
    save_observation,
    load_observations,
    load_observations_by_time_range,
)

# ── hypotheses ──
from .hypotheses import (  # noqa: F401
    save_hypothesis,
    update_hypothesis_evidence,
    load_active_hypotheses,
    get_expired_hypotheses,
    get_hypothesis_by_subject,
    enter_suspicion_mode,
    update_suspected_evidence,
    resolve_suspicion,
    upgrade_hypothesis_decay,
    set_hypothesis_status,
)

# ── profile / facts / user_model / relationships / trajectory ──
from .profile import (  # noqa: F401
    upsert_profile,
    load_current_profile,
    remove_profile,
    upsert_user_model,
    load_user_model,
    save_trajectory_summary,
    load_trajectory_summary,
    save_or_update_relationship,
    load_relationships,
    save_profile_fact,
    close_time_period,
    confirm_profile_fact,
    add_evidence,
    find_current_fact,
    load_suspected_profile,
    load_confirmed_profile,
    load_full_current_profile,
    load_timeline,
    get_expired_facts,
    load_disputed_facts,
    resolve_dispute,
    update_fact_decay,
)

# ── strategies ──
from .strategies import (  # noqa: F401
    save_strategy,
    load_pending_strategies,
    mark_strategy_executed,
)

# ── memory (snapshots, summaries, fact_edges) ──
from .memory import (  # noqa: F401
    load_conversation_summaries_around,
    load_summaries_by_observation_subject,
    save_memory_snapshot,
    load_memory_snapshot,
    save_fact_edge,
    load_fact_edges,
    delete_fact_edges_for,
)

# ── proactive ──
from .proactive import (  # noqa: F401
    save_proactive_log,
    load_proactive_log,
    get_last_interaction_time,
)

# ── finance ──
from .finance import (  # noqa: F401
    parse_smcc_email,
    save_finance_transaction,
    load_finance_transactions,
    update_finance_transaction,
    get_finance_summary,
    get_finance_merchant_stats,
    get_finance_category_stats,
    get_finance_overview,
    get_last_import_date,
    get_imported_email_ids,
    import_finance_from_email,
    save_merchant_category,
    load_merchant_categories,
)

# ── health ──
from .health import (  # noqa: F401
    save_withings_tokens,
    load_withings_tokens,
    save_withings_measure,
    load_withings_measures,
    save_withings_activity,
    load_withings_activity,
    save_withings_sleep,
    load_withings_sleep,
    get_last_sync_time,
    save_sync_log,
    get_health_overview,
)
