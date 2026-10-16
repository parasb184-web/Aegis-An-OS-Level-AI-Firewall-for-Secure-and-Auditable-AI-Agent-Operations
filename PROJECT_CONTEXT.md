PROJECT CONTEXT
I'm working on Aegis, a Linux daemon (Python + ctypes) that uses fanotify FAN_OPEN_PERM to intercept file opens by AI coding agents, checks them against PostgreSQL policy rules and a sliding-window risk score, and logs every decision to PostgreSQL for a FastAPI dashboard. It runs on Ubuntu under WSL2. Read the relevant files and the README fully before changing anything.

Current state of main:
- The daemon starts with: sudo python3 daemon.py ~/demo --roots /tmp/aegis_roots
- Agents are launched with ./run_agent.sh <scenario>, which writes the agent's PID into the roots file. Only processes under a registered root are judged; everything else is allowed as "not supervised".
- Risk window is per supervised root. WINDOW = 10s, FILE_LIMIT = 15, BLOCK_AT = 40, WARN_AT = 30. Verdicts are allow, warn, block.
- /counts reads a verdict_counts summary table maintained by a trigger (Kushagra's work). It already returns "warn".
- writer.py: daemon=True thread, queue.Queue, batches of 50 or every 2 s. No try/except around write_batch/commit, no flush on shutdown. Rows are lost on Ctrl+C, and any DB error kills the writer thread silently. Ctrl+C on the daemon currently shows a KeyboardInterrupt traceback.
- Per-open latency of the daemon has never been measured.

MY ROLE
I'm Kashish, owner of the web module (I originally built api.py and dashboard.html). I'm doing the latency benchmark, the reliable audit writer, and the dashboard scenario buttons.

GIT RULES (strict)
- Never commit or push to main. Paras merges all PRs; don't merge anything yourself.
- If I have any old local branches from earlier attempts, don't reuse them. Start fresh from an up-to-date main.
- Two branches, one after the other:
  1) kashish/latency-and-writer: writer.py, daemon.py (ONLY the SIGINT/SIGTERM shutdown hook), new bench/ and results/latency/
  2) kashish/scenario-launcher: api.py (new endpoint only; don't change /counts), dashboard.html. Create it from main AFTER branch 1 is merged.
- Don't edit db.py, schema.sql, sql/ (Kushagra), risk.py, run_agent.sh (Paras) or tests/ (Mansi). If something there needs to change, stop and tell me.
- Small commits with clear messages. Push and open a PR into main for each branch (gh pr create if available; otherwise give me the GitHub link). PR description: what changed, why, how it was tested, real measured results.
- Never commit passwords, tokens, or PGPASSWORD values.

CODE STYLE
Plain readable Python. Simple loops, no classes unless needed, no async, no type hints. Comments explain why, not what.

HONESTY
Never invent results. You can't run sudo; give me exact commands, and use only output I paste back.

LEARNING
I must explain this in a viva. Before coding, explain the plan in plain words and wait for my OK. After each change, explain what it does and why in 3-5 sentences. At the end of each branch, give me 5 likely examiner questions with short answers.

BRANCH 1: kashish/latency-and-writer

TASK 1: Latency benchmark (bench/latency.py)
- Open and close the same file N times (default 2000), timing each open with time.perf_counter_ns().
- Report median, p95, p99 and max in microseconds, and record whether each open was allowed or blocked so results are never mixed.
- Runs to compare:
  a) daemon OFF
  b) daemon ON, benchmark NOT supervised (run with python3 directly)
  c) daemon ON, benchmark supervised (launched the same way run_agent.sh registers a root), file matching an allow rule
- Problem: 2000 fast supervised opens will trip FILE_LIMIT = 15, so we'd be timing denials. Explain this, then propose options (e.g. bursts of 10 opens with pauses longer than the 10 s window, or measuring allowed and blocked opens separately). Do NOT change risk.py; if a test setting is needed there, tell me so I can ask Paras.
- Save raw output to results/latency/ and write results/latency/SUMMARY.md with a table and 3-4 sentences on what the numbers mean for the design.

TASK 2: Make writer.py reliable
- Wrap write_batch + commit in try/except: on error, rollback, print a clear error, wait briefly, reconnect, and retry the batch without killing the thread. No tight infinite loop if the database stays down.
- Add stop(): put a sentinel on the queue; writer_loop drains the queue, flushes the last batch, commits and exits. Explain whether the thread should stay daemon=True.
- In daemon.py, handle SIGINT/SIGTERM: call writer.stop(), wait for the thread with a timeout, exit cleanly (no KeyboardInterrupt traceback). Change nothing else in daemon.py.
- Tests (I run them; report real results):
  1. Queue 30 records, stop within 1 second, confirm all 30 rows are in the actions table (count before and after).
  2. Stop PostgreSQL while records are queued, confirm the writer survives and logs errors, restart PostgreSQL, confirm the rows arrive.
  3. Run the daemon, run ./run_agent.sh massread, press Ctrl+C right after: no traceback, and the rows logged match the decisions printed.
- Explain what this still can't protect against (kill -9, power cut).

BRANCH 2: kashish/scenario-launcher (after branch 1 is merged)

TASK 3: Dashboard scenario buttons
- In api.py, add POST /run/{scenario}: only "normal", "credentials" and "massread" allowed, anything else gets a 400. No shell=True, no sudo.
- Start fake_agent.py with subprocess.Popen and register proc.pid in the roots file the same way run_agent.sh does, so the daemon supervises exactly that run (not uvicorn). Read run_agent.sh and the README first to match the format.
- Refuse to start a second scenario while one is still running.
- In dashboard.html, add three buttons and a short status message ("running...", "already running", "error").

TASK 4: Show "warn" on the dashboard
- Add a warn counter and show warn rows in amber in the activity list, next to allow and block. Keep the existing filter and pause working.

TESTS for branch 2 (I run them)
- With the daemon running: each button gives normal = allowed, credentials = blocked, massread = blocked partway (about 15 allowed, then blocked).
- POST /run/anything-else is rejected.
- Clicking a button while a scenario is running shows "already running".
