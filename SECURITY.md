# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` branch | ✅ Yes |
| Older releases | ❌ No |

---

## Reporting a Vulnerability

If you discover a security vulnerability in **Aegis**, please **do not** open a public GitHub issue.

Instead, report it privately by emailing the maintainer or opening a [GitHub Security Advisory](https://github.com/parasb184-web/Aegis-An-OS-Level-AI-Firewall-for-Secure-and-Auditable-AI-Agent-Operations/security/advisories/new).

Please include:

1. A clear description of the vulnerability.
2. Steps to reproduce the issue.
3. The potential impact (data exposure, privilege escalation, etc.).
4. Any suggested remediation if known.

We aim to acknowledge reports within **48 hours** and to provide a fix or workaround within **7 days** for critical issues.

---

## Threat Model

Aegis is designed to intercept file-open events from AI agent processes running on Linux.  
The following are **in scope** for security considerations:

- Bypass of fanotify monitoring via process forking or namespace tricks.
- SQL injection via crafted process names or file paths recorded in the audit log.
- Privilege escalation from the daemon's root-level fanotify descriptor.
- Unauthenticated access to the FastAPI REST API (no auth layer by default — deploy behind a firewall or reverse proxy in production).

The following are **out of scope**:

- Security of the host OS itself.
- PostgreSQL authentication hardening (users are responsible for DB credentials).
- Network-level security of the monitoring dashboard.

---

## Hardening Recommendations

- Run the FastAPI server behind a reverse proxy (nginx/Caddy) with TLS.
- Restrict PostgreSQL access to `localhost` only.
- Set the `AEGIS_DB` environment variable instead of hardcoding credentials.
- Rotate the `aegis` database password periodically.
- Monitor `/tmp/aegis_status.json` for unexpected daemon restarts.

