.PHONY: test test-quick lint setup-db clean

test:
	python3 tests/test_imports.py
	python3 tests/test_unit.py
	python3 tests/test_storage.py

test-quick:
	python3 tests/test_imports.py
	python3 tests/test_unit.py

lint:
	python3 -m ruff check agent/ tests/

setup-db:
	python3 setup_db.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name '*.pyc' -delete 2>/dev/null; true
