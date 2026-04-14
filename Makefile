.PHONY: start stop test test-quick lint setup-db clean

start:
	@python3 scripts/start_local.py

stop:
	@pkill -f "agent.api|web.py|agent.telegram_bot|agent.discord_bot" 2>/dev/null || true
	@echo "[stop] All services stopped."

test:
	python3 tests/test_imports.py
	python3 tests/test_parsing.py
	python3 tests/test_maturity.py
	python3 tests/test_synonyms.py
	python3 tests/test_profile_filter.py
	python3 tests/test_perceive.py
	python3 tests/test_trajectory.py
	python3 tests/test_think.py
	python3 tests/test_disputes.py
	python3 tests/test_formatting.py
	python3 tests/test_session_memory.py
	python3 tests/test_storage.py

test-quick:
	python3 tests/test_imports.py
	python3 tests/test_parsing.py
	python3 tests/test_maturity.py
	python3 tests/test_synonyms.py
	python3 tests/test_profile_filter.py
	python3 tests/test_perceive.py
	python3 tests/test_trajectory.py
	python3 tests/test_think.py
	python3 tests/test_disputes.py
	python3 tests/test_formatting.py
	python3 tests/test_session_memory.py

lint:
	python3 -m ruff check agent/ tests/

setup-db:
	python3 setup_db.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name '*.pyc' -delete 2>/dev/null; true
