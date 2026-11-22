# Aegis: OS-Level AI Firewall

An OS-level security firewall for secure, auditable, and rate-limited AI coding agent operations.

Aegis sits between a supervised process and the files it attempts to open. Linux pauses each `open()` syscall in kernel space and asks Aegis for permission; Aegis evaluates the target path against security policies in PostgreSQL and a sliding-window behavioral risk score, responds to the kernel, and logs the decision for live auditing on the web dashboard.

Because it uses Linux fanotify in permission inspection mode (`FAN_OPEN_PERM`), blocked files are never read — the `open()` call fails with `EPERM` before any bytes reach the agent process.

---

## Architecture Overview

```text
+--------------------------------------------------------------------+
|                            LINUX KERNEL                            |
|                                                                    |
|    AI Agent Process                                                |
|           |                                                        |
|         open()                                                     |
|           v                                                        |
|    [ FAN_OPEN_PERM ] --------------> fan_fd (blocks caller)       |
|           ^                                    |                   |
|           | FAN_ALLOW / FAN_DENY               v                   |
+-----------|------------------------------------|-------------------+
            |                                    |
+-----------|------------------------------------|-------------------+
|           |          AEGIS DAEMON (daemon.py)  |                   |
|           |                                    v                   |
|           +--- 1. Identify Process (walk /proc/<pid>/stat)         |
|                2. Check Database Policies (db.py)                  |
|                3. Calculate Sliding-Window Risk (risk.py)          |
|                4. Respond with FAN_ALLOW or FAN_DENY               |
|                5. Enqueue decision for audit (writer.py)           |
|                                   |                                |
|                                   v                                |
|                [ Thread-Safe Batch Writer Queue ]                  |
|                                   |                                |
|                                   v                                |
|                         POSTGRESQL DATABASE                        |
|                         - policies (rules)                         |
|                         - actions (audit log)                      |
|                         - verdict_counts (auto-triggers)           |
+--------------------------------------------------------------------+
                                    |
                                    v
+--------------------------------------------------------------------+
|                         FASTAPI & DASHBOARD                        |
|                     Uvicorn Server (port 8000)                     |
|                 Real-Time Security Operations UI                   |
+--------------------------------------------------------------------+
```

For full architectural details, see [ARCHITECTURE.md](file:///c:/Users/HP%20VICTUS/OneDrive/Desktop/PBL%20Project/Aegis-An-OS-Level-AI-Firewall-for-Secure-and-Auditable-AI-Agent-Operations/ARCHITECTURE.md).

---

## What It Supervises

Aegis judges a **process tree**, not a folder. You register one PID as the agent root; Aegis supervises that process and all children it spawns.

For each file open event, Aegis walks up the process parent chain in `/proc/<pid>/stat`:
- **Reaches a registered root** $\rightarrow$ Supervised agent process: apply security policies and risk score.
- **Reaches init (PID 1) without finding a root** $\rightarrow$ Unsupervised process (e.g. editor, shell, background system service): allow immediately with `"not supervised"`.

This design ensures your editor, terminal shell, and compiler remain unaffected while the agent process is watched.

---

## Requirements

- **Operating System:** Linux with `fanotify` permission events enabled (Ubuntu 22.04+ or WSL2 on Windows).
- **Python:** 3.10+ with packages listed in `requirements.txt`.
- **Database:** PostgreSQL with a database and user named `aegis`.
- **Permissions:** Root access (`sudo`), required by `fanotify` for `CAP_SYS_ADMIN`.

---

## Quickstart

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up the Database

```bash
# Initialize database schema and tables
psql -U aegis -d aegis -h localhost -f schema.sql

# Verify database health
python3 scripts/verify_db.py
```

### 3. Initialize Demo Workspace

```bash
# Creates ~/demo directory with sample workspace, credentials, and notes
./scripts/setup_demo.sh
```

---

## Running Aegis

### Step 1: Start the Web Dashboard & API

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser to view the real-time security dashboard.

### Step 2: Start the Kernel Monitoring Daemon

In a second terminal with root privileges:

```bash
sudo python3 daemon.py ~/demo
```

### Step 3: Run Agent Scenarios

In a third terminal (or directly from the one-click buttons on the web dashboard):

```bash
./run_agent.sh normal
./run_agent.sh credentials
./run_agent.sh massread
```

---

## Scenarios

| Scenario | What It Does | Expected Verdict |
|---|---|---|
| **`normal`** | Reads 3 files in `project/src`, 1.5s apart | All **`ALLOW`** (matches workspace policy) |
| **`credentials`** | Reads workspace file, then attempts `~/.ssh/id_rsa` | **`BLOCK`** (matches SSH key policy rule) |
| **`massread`** | Attempts rapid read across 80 files in 6 folders (0.05s apart) | **`BLOCK`** (risk score $\ge 40$, triggers rate limit) |

---

## Verdicts & Risk Scoring

| Verdict | Kernel Action | Meaning |
|---|:---:|---|
| **`allow`** | `FAN_ALLOW` | Explicit policy permit, or no matching rule. |
| **`warn`** | `FAN_ALLOW` | Warning issued (risk score 30–39); agent is wandering across folders. |
| **`block`** | `FAN_DENY` | Access refused (`EPERM`); triggered by explicit block policy or high risk ($\ge 40$). |

### Risk Heuristics

Aegis tracks a 10-second rolling window across the supervised process tree:

| Signal | Score Points |
|---|:---:|
| Velocity: $> 15$ file opens in 10s | **+40 points** |
| Dispersion: $> 4$ distinct directories in 10s | **+30 points** |

The entire agent tree shares one sliding window to prevent agents from evading rate limits by forking child worker processes.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/counts` | Returns aggregate counts: `allow`, `warn`, `block`. |
| `GET` | `/recent` | Returns the 50 most recent decisions for the audit feed. |
| `GET` | `/verdict/{v}` | Top files and reasons filtered by verdict (`allow`, `warn`, `block`). |
| `GET` | `/sessions` | Historical sessions grouped by process tree PID. |
| `GET` | `/session/{pid}` | Chronological decision sequence for a specific session PID. |
| `GET` | `/rules` | Configured policies with real-time trigger frequencies. |
| `GET` | `/daemon` | Heartbeat, watched directory, and active agent status. |
| `POST` | `/run/{scenario}` | Triggers a demo scenario execution (`normal`, `credentials`, `massread`). |
| `GET` | `/` | Serves the HTML5 Security Operations Dashboard. |

---

## Running Automated Tests

```bash
# Run all unit tests
python3 -m unittest discover -s tests -p "test_*.py"
```

---

## Known Limitations

- **Roots file is user-writable:** An agent running under the same user can append PIDs to `/tmp/aegis_roots`. It cannot remove itself, but could add PIDs.
- **Double-fork:** A process that double-forks and lets the middle parent terminate is re-parented to PID 1 (init), bypassing the ancestry check. Cgroup-based tracking would resolve this.
- **Dynamic folder creation:** Monitored directories are scanned and marked upon daemon startup. Subdirectories created dynamically after startup require a restart.
- **Fail-open design:** If the daemon terminates or crashes, pending kernel events are unblocked to prevent system-wide hangs.
