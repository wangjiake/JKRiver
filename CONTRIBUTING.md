# Contributing to Riverse

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
git clone https://github.com/wangjiake/JKRiver.git
cd JKRiver
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Set up PostgreSQL and configure `settings.yaml`:

```bash
createdb -h localhost -U YOUR_USERNAME Riverse
psql -h localhost -U YOUR_USERNAME -d Riverse -f agent/schema.sql
cp settings.yaml.default settings.yaml
# Edit settings.yaml with your database credentials
```

## Running Tests

| Test file | What it covers | Requirements |
|---|---|---|
| `tests/test_imports.py` | All packages import correctly | None |
| `tests/test_unit.py` | Pure unit tests (no I/O) | None |
| `tests/test_db.py` | Database connection and schema | PostgreSQL |
| `tests/test_storage.py` | Storage layer integration | PostgreSQL |
| `tests/test_sleep_pipeline.py` | Sleep pipeline steps | PostgreSQL (integration) |
| `tests/test_demo_pipeline.py` | End-to-end pipeline | PostgreSQL + LLM |

### Quick Check (no database needed)

```bash
python tests/test_imports.py
python tests/test_unit.py
```

These two must pass before submitting a PR.

## Code Style

Follow the project's `.editorconfig`:

- **Python:** 4-space indent, UTF-8, LF line endings
- **YAML / JSON / Markdown:** 2-space indent
- **HTML:** 2-space indent

Keep code consistent with the existing style in each file.

## Commit Messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short summary>
```

Common types:

| Type | When to use |
|---|---|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `chore` | Build, CI, dependency updates |

Examples:

```
feat: add Japanese prompt support
fix: interest category check ignoring non-English labels
docs: fix web dashboard port in README
```

Keep the summary under 72 characters. Use the body for details if needed.

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`
2. **Write** your changes, keeping commits focused
3. **Test** — at minimum, run `test_imports.py` and `test_unit.py`
4. **Submit** a PR against `main` with a clear description of what and why

### PR Checklist

- [ ] Code follows existing style (`.editorconfig`)
- [ ] `test_imports.py` passes
- [ ] `test_unit.py` passes
- [ ] New features include tests where applicable
- [ ] No new warnings introduced

## License

By contributing, you agree that your contributions will be licensed under the [AGPL-3.0](LICENSE) license.
