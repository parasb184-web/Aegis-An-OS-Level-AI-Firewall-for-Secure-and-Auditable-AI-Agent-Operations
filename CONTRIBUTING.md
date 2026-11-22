# Contributing to Aegis

Thank you for your interest in contributing to **Aegis — an OS-Level AI Firewall**!  
This document explains how to set up the development environment and what guidelines to follow when submitting changes.

---

## Prerequisites

| Tool | Version |
|------|---------|
| Python | 3.10 + |
| PostgreSQL | 14 + |
| Linux kernel (WSL2 or bare-metal) | 5.1 + (fanotify FAN_OPEN_PERM support) |
| pip / venv | latest |

---

## Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/parasb184-web/Aegis-An-OS-Level-AI-Firewall-for-Secure-and-Auditable-AI-Agent-Operations.git
cd Aegis-An-OS-Level-AI-Firewall-for-Secure-and-Auditable-AI-Agent-Operations

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create the database
psql -U postgres -c "CREATE USER aegis WITH PASSWORD 'aegis';"
psql -U postgres -c "CREATE DATABASE aegis OWNER aegis;"
psql -U aegis -d aegis -f schema.sql
```

---

## Running Tests

```bash
python3 -m unittest discover -s tests -p "test_*.py"
```

All tests must pass before opening a pull request.

---

## Coding Guidelines

- **Python style**: Follow [PEP 8](https://peps.python.org/pep-0008/).  
- **Type hints**: Use `from typing import ...` annotations on all public functions.  
- **Docstrings**: Every public function should have a one-line summary docstring.  
- **No functional regressions**: Changes must not alter the verdict logic, database schema, or REST API contracts.  
- **Commit messages**: Use [Conventional Commits](https://www.conventionalcommits.org/) format (`feat:`, `fix:`, `docs:`, `chore:`, etc.).

---

## Branch Naming

| Purpose | Pattern |
|---------|---------|
| Feature | `feature/<short-description>` |
| Bug fix | `fix/<short-description>` |
| Documentation | `docs/<short-description>` |

---

## Pull Request Checklist

- [ ] All tests pass locally  
- [ ] No duplicate or dead code introduced  
- [ ] Docstrings and type hints added/updated  
- [ ] `CHANGELOG.md` updated with a brief entry  
- [ ] No secrets or credentials committed  

---

## Questions?

Open an issue on GitHub and tag it with the `question` label.
