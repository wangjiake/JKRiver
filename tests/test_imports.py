"""Verify all refactored packages import correctly.

Usage:
    python -m pytest tests/test_imports.py -v
    python tests/test_imports.py            # standalone
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── sleep package ──

def test_sleep_package_import():
    from agent.sleep import run_async
    assert callable(run_async)


def test_sleep_submodules():
    modules = [
        "agent.sleep._parsing",
        "agent.sleep._formatting",
        "agent.sleep._maturity",
        "agent.sleep._data_access",
        "agent.sleep.extractors",
        "agent.sleep.analysis",
        "agent.sleep.disputes",
        "agent.sleep.trajectory",
        "agent.sleep.orchestration",
    ]
    for mod in modules:
        m = importlib.import_module(mod)
        assert m is not None, f"Failed to import {mod}"


def test_sleep_orchestration_exports():
    from agent.sleep.orchestration import run, run_async
    assert callable(run)
    assert callable(run_async)


# ── storage package ──

def test_storage_db():
    from agent.storage._db import get_db_connection, _get_db_config
    assert callable(get_db_connection)
    cfg = _get_db_config()
    assert isinstance(cfg, dict)
    assert "dbname" in cfg


def test_storage_public_api():
    from agent.storage import (
        get_db_connection,
        save_raw_conversation,
        save_conversation_turn,
        save_event,
        load_active_events,
        save_observation,
        load_observations,
        upsert_profile,
        load_current_profile,
        save_strategy,
        load_pending_strategies,
        save_trajectory_summary,
        load_trajectory_summary,
        save_or_update_relationship,
        load_relationships,
        upsert_user_model,
        load_user_model,
    )
    for fn in [save_raw_conversation, save_conversation_turn, save_event,
               load_active_events, save_observation, load_observations,
               upsert_profile, load_current_profile, save_strategy,
               load_pending_strategies, save_trajectory_summary,
               load_trajectory_summary, save_or_update_relationship,
               load_relationships, upsert_user_model, load_user_model]:
        assert callable(fn), f"{fn} is not callable"


def test_storage_submodules():
    modules = [
        "agent.storage._db",
        "agent.storage._synonyms",
        "agent.storage.conversation",
        "agent.storage.events",
        "agent.storage.observations",
        "agent.storage.profile",
        "agent.storage.strategies",
        "agent.storage.memory",
        "agent.storage.proactive",
        "agent.storage.finance",
        "agent.storage.health",
    ]
    for mod in modules:
        m = importlib.import_module(mod)
        assert m is not None, f"Failed to import {mod}"


# ── cognition ──

def test_cognition_engine():
    from agent.cognition import CognitionEngine
    from agent.config import load_config
    config = load_config()
    engine = CognitionEngine(config)
    assert hasattr(engine, "perceive")
    assert hasattr(engine, "perceive_async")
    assert hasattr(engine, "think_async")
    assert hasattr(engine, "analyze_trajectory_async")


# ── config ──

def test_config_loads():
    from agent.config import load_config
    config = load_config()
    assert "llm" in config
    assert "database" in config
    assert config.get("language") in ("zh", "en", "ja")


# ── embedding / clustering ──

def test_embedding_module():
    from agent.utils.embedding import (
        get_embedding, embed_all_memories, vector_search,
    )
    assert callable(get_embedding)
    assert callable(embed_all_memories)
    assert callable(vector_search)


def test_clustering_module():
    from agent.utils.clustering import cluster_memories, load_cluster_themes
    assert callable(cluster_memories)
    assert callable(load_cluster_themes)


# ── web package (only if flask installed) ──

def test_web_package():
    try:
        import flask  # noqa: F401
    except ImportError:
        print("SKIP: flask not installed")
        return

    from web import create_app
    app = create_app()
    rules = [r.rule for r in app.url_map.iter_rules() if r.rule != "/static/<path:filename>"]
    assert len(rules) >= 10, f"Expected >=10 routes, got {len(rules)}"

    from web.core import core_bp
    from web.profile import profile_bp
    from web.snapshot import snapshot_bp
    from web.observations import observations_bp
    from web.review import review_bp
    from web.finance import finance_bp
    from web.health import health_bp
    for bp in [core_bp, profile_bp, snapshot_bp, observations_bp,
               review_bp, finance_bp, health_bp]:
        assert bp is not None


# ── standalone runner ──

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for fn in tests:
        name = fn.__name__
        try:
            fn()
            print(f"  PASS  {name}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
