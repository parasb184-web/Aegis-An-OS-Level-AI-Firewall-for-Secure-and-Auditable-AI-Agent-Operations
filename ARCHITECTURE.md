# Aegis System Architecture

Aegis is an OS-level security firewall designed to protect local developer environments from untrusted, autonomous, or compromised AI coding agents.

---

## 1. High-Level Design

Unlike userland proxies or network-only sandboxes, Aegis operates directly at the operating system kernel boundary using the Linux **`fanotify`** subsystem in permission inspection mode (`FAN_OPEN_PERM`).

```text
+-------------------------------------------------------------+
|                        LINUX KERNEL                         |
|                                                             |
|   Supervised Agent Process                                  |
|         |                                                   |
|       open()                                                |
|         v                                                   |
|   [ FAN_OPEN_PERM ] --------------> fan_fd (blocks caller)  |
|         ^                                     |             |
|         | FAN_ALLOW / FAN_DENY                v             |
+---------|-------------------------------------|-------------+
          |                                     |
+---------|-------------------------------------|-------------+
|         |          AEGIS DAEMON (daemon.py)   |             |
|         |                                     v             |
|         +-- 1. Identify process (walk /proc/<pid>/stat)     |
|             2. Check PostgreSQL policies (db.py)            |
|             3. Evaluate sliding-window risk score (risk.py) |
|             4. Respond to kernel with FAN_ALLOW / FAN_DENY  |
|             5. Enqueue decision for audit (writer.py)       |
|                               |                             |
|                               v                             |
|             [ Thread-Safe Batch Writer Queue ]              |
|                               |                             |
|                               v                             |
|                      POSTGRESQL DATABASE                    |
|                      - actions (audit log)                  |
|                      - policies (firewall rules)            |
|                      - verdict_counts (auto trigger)        |
+-------------------------------------------------------------+
                                |
                                v
+-------------------------------------------------------------+
|                      FASTAPI BACKEND & UI                   |
|                   Uvicorn Server (port 8000)                |
|               HTML5 / CSS Security Operations Dashboard     |
+-------------------------------------------------------------+
```

---

## 2. Kernel Interception Loop (`daemon.py`)

1. **Initialization (`start_fanotify`)**:
   - Opens a fanotify file descriptor with `FAN_CLOEXEC | FAN_CLASS_CONTENT`.
   - Requires `CAP_SYS_ADMIN` privileges.
2. **Watch Registration (`watch_folder`)**:
   - Marks target root directories with `FAN_MARK_ADD | FAN_OPEN_PERM | FAN_EVENT_ON_CHILD`.
   - When any process attempts to open a file under the watched hierarchy, the calling thread is blocked in kernel space.
3. **Event Reading (`EVENT_FORMAT = "<IBBHQii"`)**:
   - Reads `struct fanotify_event_metadata` from the descriptor:
     - `event_len`: Size of the event record.
     - `event_fd`: Open file descriptor to the target file.
     - `pid`: Process ID initiating the access.
4. **Resolution**:
   - Resolves target filesystem path via `readlink("/proc/self/fd/<fd>")`.
   - Reads process name via `/proc/<pid>/comm`.
5. **Answer**:
   - Responds to the kernel via `os.write(fan_fd, struct.pack("<iI", event_fd, verdict))`.
   - Returns `FAN_ALLOW` (0x01) or `FAN_DENY` (0x02, causing `open()` to fail with `EPERM`).

---

## 3. Process Supervision & Parent Tree Walking

Aegis avoids monitoring unrelated system utilities or editor processes by tracking **agent root process trees**:
- When an agent scenario begins, its root PID is appended to `/tmp/aegis_roots`.
- For every intercepted file event, Aegis reads `/proc/<pid>/stat`, strips the process name, and extracts the PPID (parent PID).
- Aegis walks up the process tree up to `MAX_DEPTH = 40`:
  - If a registered root PID is encountered: the process is classified as **supervised**.
  - If PID 1 (init/systemd) is reached without finding a root: the process is **unsupervised** and granted an immediate `ALLOW` with reason `"not supervised"`.
- Results are cached in `supervised_cache` to ensure sub-millisecond evaluation on repeat accesses.

---

## 4. Policy Engine (`db.py`)

Security policies are loaded from the PostgreSQL `policies` table ordered by action precedence:
```sql
SELECT path_pattern, sensitivity, action, note 
FROM policies 
ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id;
```
- SQL `%` wildcards are converted to Python `fnmatch` `*` patterns.
- High-priority `block` rules are evaluated first. If any block rule matches, the access is immediately denied.
- Explicit `allow` rules are evaluated next.
- If no rules match, the access defaults to `allow` with reason `"no rule"`.

---

## 5. Dynamic Sliding-Window Risk Engine (`risk.py`)

Aegis implements an anomaly detection engine to guard against exfiltration and directory scraping:
- **Rolling Window**: 10.0 seconds.
- **Velocity Limit**: 15 file opens per window.
- **Dispersion Limit**: 4 distinct folders per window.
- **Scoring**:
  - Exceeding file limit: **+40 points**.
  - Exceeding folder limit: **+30 points**.
  - Combined max score: **70 points**.
- **Enforcement**:
  - Score $\ge 40$ (`BLOCK_AT`): Hard `FAN_DENY` block.
  - Score $30 \le \text{pts} < 40$ (`WARN_AT`): `FAN_ALLOW` with warning audit note.

---

## 6. Asynchronous Audit Writer Pipeline (`writer.py`)

Database writes are decoupled from the real-time kernel interception path:
- Interception loop pushes `(pid, process_name, path, verdict, reason)` into a thread-safe `queue.Queue`.
- A dedicated background worker thread drains the queue.
- Flushes records in batches of `BATCH_SIZE = 50` or after `FLUSH_SECONDS = 2.0`.
- Implements automatic retry with exponential backoff on transient database disconnects.

---

## 7. Database Aggregation Triggers (`schema.sql`)

PostgreSQL maintains pre-computed metrics to ensure instant dashboard updates:
- Table `actions`: Stores full immutable audit log.
- Table `verdict_counts`: Maintained by trigger `actions_count_verdict`. Every insert into `actions` increments `verdict_counts.n` in the same transaction.
- Guarantees $O(1)$ dashboard tally polling without full table scans.
