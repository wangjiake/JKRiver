from dataclasses import dataclass, field
from agent.storage._synonyms import _get_category_synonyms, _get_subject_synonyms


@dataclass
class _PipelineState:
    """Mutable state bag passed through all sleep-pipeline steps."""

    # Inputs (set at init)
    session_convs: dict
    config: dict
    language: str
    L: dict

    # Accumulated data
    all_msg_ids: list = field(default_factory=list)
    all_convs: list = field(default_factory=list)
    all_observations: list = field(default_factory=list)

    # Profile state
    existing_profile: list = field(default_factory=list)
    current_profile: list = field(default_factory=list)
    trajectory: dict | None = None

    # Analysis results
    behavioral_signals: list = field(default_factory=list)
    changed_items: list = field(default_factory=list)
    affected_fact_ids: set = field(default_factory=set)
    new_fact_count: int = 0
    latest_conv_time: object = None  # datetime or None

    # Post-processing counters
    confirmed_count: int = 0
    dispute_resolved: int = 0
    pipeline_errors: int = 0


def _build_fact_lookup(profile: list[dict]) -> dict[tuple[str, str], dict]:
    """Build an in-memory lookup dict from profile facts, keyed by (cat_lower, subj_lower).

    Also indexes all synonym variants so that find_current_fact() can be replaced
    with an O(1) lookup during behavioral pattern analysis.
    """
    lookup: dict[tuple[str, str], dict] = {}
    for fact in profile:
        cat = (fact.get("category") or "").strip().lower()
        subj = (fact.get("subject") or "").strip().lower()
        if not cat or not subj:
            continue
        # Primary key
        key = (cat, subj)
        if key not in lookup:
            lookup[key] = fact

        # Also index synonym variants
        cat_syns = _get_category_synonyms(fact.get("category", ""))
        subj_syns = _get_subject_synonyms(fact.get("subject", ""))
        for cs in cat_syns:
            for ss in subj_syns:
                syn_key = (cs.strip().lower(), ss.strip().lower())
                if syn_key not in lookup:
                    lookup[syn_key] = fact
    return lookup


def _find_fact_in_profile(lookup: dict[tuple[str, str], dict],
                          category: str, subject: str) -> dict | None:
    """O(1) fact lookup using the pre-built synonym dict."""
    key = (category.strip().lower(), subject.strip().lower())
    return lookup.get(key)
