"""Synonym resolution for category and subject normalization.

Loads multilingual synonym groups from agent/config/synonyms.yaml and
flattens zh+en+ja into unified sets.  Public API is unchanged:
  _CATEGORY_SYNONYM_GROUPS, _SUBJECT_SYNONYM_GROUPS,
  _get_category_synonyms(), _get_subject_synonyms(),
  is_significant_category()
"""

import os
import yaml

_YAML_PATH = os.path.join(
    os.path.dirname(__file__), os.pardir, "config", "synonyms.yaml"
)

with open(_YAML_PATH, encoding="utf-8") as _f:
    _CFG = yaml.safe_load(_f)


def _flatten_groups(raw_groups: list[dict]) -> list[set[str]]:
    """Merge zh/en/ja lists in each group into one frozenset."""
    result = []
    for g in raw_groups:
        merged: set[str] = set()
        for lang in ("zh", "en", "ja"):
            merged.update(g.get(lang, []))
        result.append(merged)
    return result


def _build_map(groups: list[set[str]]) -> dict[str, set[str]]:
    m: dict[str, set[str]] = {}
    for group in groups:
        for name in group:
            m[name] = group
    return m


_CATEGORY_SYNONYM_GROUPS = _flatten_groups(_CFG["category_groups"])
_SUBJECT_SYNONYM_GROUPS = _flatten_groups(_CFG["subject_groups"])

_CAT_SYNONYM_MAP = _build_map(_CATEGORY_SYNONYM_GROUPS)
_SUBJ_SYNONYM_MAP = _build_map(_SUBJECT_SYNONYM_GROUPS)


def _get_category_synonyms(category: str) -> set[str]:
    return _CAT_SYNONYM_MAP.get(category, {category})


def _get_subject_synonyms(subject: str) -> set[str]:
    return _SUBJ_SYNONYM_MAP.get(subject, {subject})


# ── Significant-category check ──────────────────────────
# Categories where a change should trigger earlier trajectory updates.

_sig_anchors_cfg = _CFG.get("significant_anchors", {})
_SIGNIFICANT_CATEGORY_ANCHORS = frozenset(
    _sig_anchors_cfg.get("zh", [])
    + _sig_anchors_cfg.get("en", [])
    + _sig_anchors_cfg.get("ja", [])
)

_SIGNIFICANT_CATEGORIES: set[str] = set()
for _anchor in _SIGNIFICANT_CATEGORY_ANCHORS:
    _SIGNIFICANT_CATEGORIES |= _CAT_SYNONYM_MAP.get(_anchor, {_anchor})


def is_significant_category(category: str) -> bool:
    """Check if a category is 'significant' (career, family, location, etc.)."""
    return category in _SIGNIFICANT_CATEGORIES or category.lower() in _SIGNIFICANT_CATEGORIES
