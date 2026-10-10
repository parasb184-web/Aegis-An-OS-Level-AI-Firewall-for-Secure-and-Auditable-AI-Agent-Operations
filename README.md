# Aegis

An OS-level firewall for AI coding agents.

Aegis sits between a supervised process and the files it opens. Linux pauses
each `open()` and asks Aegis for permission; Aegis checks the path against
policy rules in PostgreSQL and against a short-term risk score, answers the
kernel, and then records the decision for the dashboard.

It uses fanotify in permission mode (`FAN_OPEN_PERM`), so a blocked file is
never read — the open fails with `EPERM` before any bytes reach the agent.

## What it supervises

Aegis judges a **process tree**, not a folder. You register one pid as the
agent root; Aegis supervises that process and everything it starts.

For each open, Aegis walks up the parent chain in `/proc/<pid>/stat`:

- reaches a registered root -> this is the agent, apply policy and risk
- reaches init first -> somebody else, allow and log `not supervised`

This is what keeps your own shell, your editor and background system
processes out of the way while the agent is being watched.

## Requirements

- Linux with fanotify permission events (works under WSL2)
- Python 3 with `psycopg2`, `fastapi`, `uvicorn`
- PostgreSQL, with a database and user named `aegis`
- root, because fanotify permission mode needs `CAP_SYS_ADMIN`

## Setting up the database

```bash
psql -U aegis -d aegis -h localhost -f schema.sql
```

Connection settings live at the top of `db.py`.

## Running it

Three terminals. Order matters: start the daemon first.

**1. The daemon**

```bash
sudo python3 daemon.py ~/demo
```

It marks every folder under `~/demo`, loads the policy rules, and waits.
To use a different roots file:

```bash
sudo python3 daemon.py ~/demo --roots /tmp/aegis_roots
```

**2. The agent**

```bash
./run_agent.sh normal
./run_agent.sh credentials
./run_agent.sh massread
```

`run_agent.sh` appends its own pid to the roots file and then `exec`s the
agent, so the pid it registered is the pid the agent runs under. Running
`python3 fake_agent.py ...` directly works too, but it will be treated as
unsupervised and nothing will be blocked.

**3. The dashboard**

```bash
uvicorn api:app --reload --port 8000
```

Then open <http://localhost:8000>.

## The scenarios

| Scenario | What it does | Expected |
|---|---|---|
| `normal` | 3 opens in `project/src`, 1.5s apart | all allowed |
| `credentials` | 1 workspace file, then `~/demo/.ssh/id_rsa` | second one blocked by policy |
| `massread` | 80 files across 6 folders, 0.05s apart | allowed until the risk score trips, then blocked |

## Verdicts

| Verdict | File opens? | Meaning |
|---|---|---|
| `allow` | yes | no rule matched, or a rule allows it |
| `warn` | yes | medium risk (score 30): wandering across folders |
| `block` | no | a policy rule says block, or the risk score reached 40 |

## Risk scoring

Aegis keeps a 10 second history of opens per supervised root. One file open
tells you nothing; the shape of a burst does.

| Signal | Points |
|---|---|
| more than 15 opens in 10s | 40 |
| more than 4 distinct folders in 10s | 30 |

The whole agent tree shares one window. Giving each process its own would
let an agent stay under the limit by forking children and splitting the
reads between them.

## Known limitations

- **The roots file is user-writable.** An agent running as your user can
  edit it. It cannot remove itself from supervision — Aegis only ever adds
  pids from the file and releases a root when `/proc/<pid>` disappears — but
  it can add pids, which only causes more processes to be supervised.
- **Double-fork escapes the ancestry check.** A process that forks twice and
  lets the middle process exit is re-parented to init, so the walk no longer
  reaches the agent root. Cgroup-based supervision would close this.
- **Folders created after startup are not watched.** The folder tree is
  walked and marked once when the daemon starts.
- **Fail-open.** If the daemon dies, the kernel releases its pending
  permission events and stops generating new ones, so opens are allowed.
- **PID reuse.** Cached answers are dropped once a second for pids that no
  longer exist, which leaves a sub-second window where a recycled pid could
  inherit the previous owner's answer.
