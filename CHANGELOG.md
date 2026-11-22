# Changelog

All notable changes to **Aegis** are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added
- `CONTRIBUTING.md` — developer setup, test, and PR guidelines.
- `SECURITY.md` — vulnerability disclosure policy.
- `ARCHITECTURE.md` — system architecture and component overview.
- `CHANGELOG.md` — this file.
- `.editorconfig` — consistent formatting rules for all editors.
- `requirements.txt` — pinned Python dependency list.
- Unit tests: `tests/test_risk.py`, `tests/test_policy.py`.
- Helper scripts: `scripts/setup_demo.sh`, `scripts/verify_db.py`.

### Changed
- `db.py`: added `__all__`, clarified `DB` constant with environment-variable note.
- `risk.py`: added `__all__`, clarified `WINDOW` constant comment.
- `writer.py`: added `__all__`; removed duplicate declarations that caused syntax errors.
- `api.py`: added section separator comments for readability.
- `daemon.py`: resolved syntax and import issues; added graceful `libc.so.6` loading fallback for Windows/Pylance compatibility.
- `README.md`: modernised with badges, architecture overview, and quickstart guide.

### Fixed
- `writer.py`: duplicate variable and function-definition lines (caused `SyntaxError`).
- `daemon.py`: duplicated function headers and constants from an improperly merged manual edit.
- `api.py`: unmatched `)` on line 84 (restored from git history).

---

## [0.1.0] — 2026-11-01

### Added
- Initial project scaffolding: `api.py`, `daemon.py`, `db.py`, `risk.py`, `writer.py`, `fake_agent.py`.
- PostgreSQL schema (`schema.sql`) with `policies`, `actions`, and `verdict_counts` tables.
- Trigger-based real-time verdict counting.
- `dashboard.html` — single-page monitoring dashboard.
- `run_agent.sh` — convenience wrapper to launch demo scenarios.
- fanotify-based file-open interception in the daemon.
- Policy engine with glob-pattern matching and block/allow/warn verdicts.
- Sliding-window risk scoring engine.
- Async batch writer with retry and reconnect logic.

