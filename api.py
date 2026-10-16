# Small web server that reads the audit log for the dashboard.
# It only reads. All the deciding happens in daemon.py.

import json
import os
import subprocess
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import db

app = FastAPI()

# The only scenarios we will start. This is a whitelist checked by exact
# membership, not a sanitising filter: anything not in this set never
# reaches subprocess at all. fake_agent.py is launched as an argument
# vector with no shell, so there is nothing for a crafted name to escape
# into even if this check were wrong.
SCENARIOS = ("normal", "credentials", "massread")

# Where run_agent.sh registers agent pids. Same resolution order, so the
# dashboard and the shell script always agree on which file the daemon reads.
ROOTS_FILE = os.environ.get("AEGIS_ROOTS", "/tmp/aegis_roots")

# Where the daemon publishes its heartbeat and live risk window. The risk
# score only exists in the daemon's memory, so this file is the only honest
# source for a score that rises as an agent reads.
STATUS_FILE = os.environ.get("AEGIS_STATUS", "/tmp/aegis_status.json")

# How far behind the heartbeat may fall before we call the daemon stopped.
# It publishes once a second, so three seconds is slack without being slow.
STATUS_STALE_AFTER = 3.0

# fake_agent.py lives next to this file, and it opens paths relative to the
# repo, so the child has to start there whatever directory uvicorn was run
# from.
AEGIS_DIR = os.path.dirname(os.path.abspath(__file__))

# One agent at a time. Two overlapping runs would share a risk window only
# if they shared a root, but they would still interleave in the log and make
# a demo impossible to read. The lock guards the check-then-start, which is
# not atomic on its own: uvicorn runs sync endpoints in a thread pool, so
# two clicks can land in parallel.
_running = None
_running_lock = threading.Lock()


@app.get("/counts")
def counts():
    conn = db.connect()
    cur = conn.cursor()
    # Read the trigger-maintained totals instead of counting the whole log
    # on every dashboard poll. See sql/counts_table.sql.
    cur.execute("SELECT verdict, n FROM verdict_counts")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result = {"allow": 0, "block": 0, "warn": 0}
    for verdict, count in rows:
        result[verdict] = count
    return result


@app.get("/recent")
def recent():
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, process_name, path, verdict, reason "
        "FROM actions ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    out = []
    for ts, process_name, path, verdict, reason in rows:
        out.append({
            "time": ts.strftime("%H:%M:%S"),
            "process": process_name,
            "path": path,
            "verdict": verdict,
            "reason": reason,
        })
    return out


@app.post("/run/{scenario}")
def run(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail="unknown scenario")

    global _running
    with _running_lock:
        # poll() is None while the child is alive. We keep the handle rather
        # than a boolean so a crashed agent does not block every later run.
        if _running is not None and _running.poll() is None:
            return {"started": False, "reason": "already running"}

        try:
            proc = subprocess.Popen(
                ["python3", "fake_agent.py", scenario], cwd=AEGIS_DIR)
        except OSError as e:
            raise HTTPException(status_code=500, detail="could not start: %s" % e)

        # Register the agent so the daemon supervises it and its children,
        # exactly as run_agent.sh does. We register the child itself rather
        # than uvicorn, so the API's own file activity never counts towards
        # the agent's risk window.
        try:
            with open(ROOTS_FILE, "a") as f:
                f.write("%d\n" % proc.pid)
        except OSError as e:
            proc.kill()
            raise HTTPException(status_code=500,
                                detail="could not register pid: %s" % e)

        _running = proc

    return {"started": True, "scenario": scenario, "pid": proc.pid}


def rows_to_dicts(cur):
    # Every read endpoint returns the same row shape, so the dashboard can
    # render any of them with one function.
    out = []
    for ts, process_name, path, verdict, reason, pid in cur.fetchall():
        out.append({
            "time": ts.strftime("%H:%M:%S"),
            "process": process_name,
            "path": path,
            "verdict": verdict,
            "reason": reason,
            "pid": pid,
        })
    return out


ROW_COLS = "ts, process_name, path, verdict, reason, pid"

# Rows from the old index experiment are synthetic padding, not decisions the
# daemon ever made. They would swamp every aggregate below, so every query
# here excludes them. The pattern matches that generator's paths only.
#
# It is passed as a bound parameter rather than inlined, because psycopg2
# treats % in the SQL text as a placeholder whenever arguments are given --
# inlining it made every parameterised query here fail with IndexError.
SYNTHETIC = "/home/%/demo/notes/dir%"
NOT_SYNTHETIC = "path NOT LIKE %s"


@app.get("/verdict/{verdict}")
def by_verdict(verdict: str):
    # Backs the clickable counters: the rows for one verdict, plus what is
    # actually driving that number.
    if verdict not in ("allow", "warn", "block"):
        raise HTTPException(status_code=400, detail="unknown verdict")

    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT " + ROW_COLS + " FROM actions WHERE verdict = %s AND "
                + NOT_SYNTHETIC + " ORDER BY id DESC LIMIT 100", (verdict, SYNTHETIC))
    rows = rows_to_dicts(cur)

    cur.execute("SELECT path, count(*) FROM actions WHERE verdict = %s AND "
                + NOT_SYNTHETIC + " GROUP BY path ORDER BY 2 DESC LIMIT 5",
                (verdict, SYNTHETIC))
    top_files = [{"path": p, "n": n} for p, n in cur.fetchall()]

    cur.execute("SELECT reason, count(*) FROM actions WHERE verdict = %s AND "
                + NOT_SYNTHETIC + " GROUP BY reason ORDER BY 2 DESC LIMIT 5",
                (verdict, SYNTHETIC))
    top_reasons = [{"reason": r, "n": n} for r, n in cur.fetchall()]

    cur.close()
    conn.close()
    return {"verdict": verdict, "rows": rows,
            "top_files": top_files, "top_reasons": top_reasons}


@app.get("/sessions")
def sessions():
    # One card per agent run. A run is one pid: the daemon records the pid
    # that opened each file, and each scenario is a fresh process.
    conn = db.connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT pid, min(process_name), min(ts), max(ts), count(*),"
        "       count(*) FILTER (WHERE verdict='allow'),"
        "       count(*) FILTER (WHERE verdict='warn'),"
        "       count(*) FILTER (WHERE verdict='block'),"
        "       count(*) FILTER (WHERE path LIKE %s),"
        "       count(*) FILTER (WHERE path LIKE %s),"
        "       count(*) FILTER (WHERE reason = 'not supervised') "
        "FROM actions WHERE " + NOT_SYNTHETIC + " "
        "GROUP BY pid ORDER BY min(ts) DESC LIMIT 40",
        ("%/.ssh/%", "%/notes/%", SYNTHETIC))

    out = []
    for (pid, proc, lo, hi, n, a, w, b, ssh, notes, unsup) in cur.fetchall():
        # The scenario name is not stored anywhere, so we infer it from which
        # files were touched. Marked as inferred in the UI, not presented as
        # recorded fact.
        if notes:
            scenario = "massread"
        elif ssh:
            scenario = "credentials"
        elif n <= 5:
            scenario = "normal"
        else:
            scenario = "unknown"
        out.append({
            "pid": pid, "process": proc, "scenario": scenario,
            "started": lo.strftime("%H:%M:%S"), "ended": hi.strftime("%H:%M:%S"),
            "total": n, "allow": a, "warn": w, "block": b,
            "supervised": unsup == 0,
        })
    cur.close()
    conn.close()
    return out


@app.get("/session/{pid}")
def session(pid: int):
    # Every row for one run, oldest first, so the dashboard can walk through
    # it in the order the daemon decided.
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT " + ROW_COLS + " FROM actions WHERE pid = %s AND "
                + NOT_SYNTHETIC + " ORDER BY id", (pid, SYNTHETIC))
    rows = rows_to_dicts(cur)
    cur.close()
    conn.close()
    return {"pid": pid, "rows": rows}


@app.get("/rules")
def rules():
    # The policy rules, with how many decisions each one actually made.
    # decide() writes the rule's note into actions.reason, so the note is
    # what links a rule to the rows it decided.
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT id, path_pattern, sensitivity, action, note "
                "FROM policies ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id")
    rules = cur.fetchall()

    cur.execute("SELECT reason, count(*) FROM actions WHERE " + NOT_SYNTHETIC +
                " GROUP BY reason", (SYNTHETIC,))
    fired = dict(cur.fetchall())

    out = []
    for rid, pattern, sens, action, note in rules:
        out.append({"id": rid, "pattern": pattern, "sensitivity": sens,
                    "action": action, "note": note, "fired": fired.get(note, 0)})

    # Decisions that no rule made, so the numbers on the page add up.
    out_other = [{"reason": r, "n": n} for r, n in fired.items()
                 if r not in [x["note"] for x in out]]
    cur.close()
    conn.close()
    return {"rules": out, "other": sorted(out_other, key=lambda x: -x["n"])}


@app.get("/history")
def history(path: str):
    # Every decision ever made about one file.
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT " + ROW_COLS + " FROM actions WHERE path = %s "
                "ORDER BY id DESC LIMIT 200", (path,))
    rows = rows_to_dicts(cur)
    cur.close()
    conn.close()
    return {"path": path, "rows": rows}


@app.get("/process/{pid}")
def process(pid: int):
    # What we can honestly say about a pid. Whether it was supervised is
    # recorded, because the daemon writes 'not supervised' as the reason.
    # The parent chain is NOT recorded anywhere, so it can only be walked
    # while the process is still alive -- which for a finished scenario it
    # is not. The dashboard labels which of the two it is showing.
    conn = db.connect()
    cur = conn.cursor()
    cur.execute("SELECT count(*), count(*) FILTER (WHERE reason='not supervised'),"
                "       min(process_name), min(ts), max(ts) "
                "FROM actions WHERE pid = %s AND " + NOT_SYNTHETIC, (pid, SYNTHETIC))
    total, unsup, proc, lo, hi = cur.fetchone()
    cur.close()
    conn.close()

    chain = []
    walk = pid
    depth = 0
    while walk > 1 and depth < 40:
        try:
            with open("/proc/%d/stat" % walk) as f:
                line = f.read()
            with open("/proc/%d/comm" % walk) as f:
                name = f.read().strip()
        except OSError:
            break                       # not running any more
        close = line.rfind(")")
        fields = line[close + 1:].split()
        chain.append({"pid": walk, "name": name})
        walk = int(fields[1]) if len(fields) > 1 else 0
        depth = depth + 1

    return {
        "pid": pid,
        "process": proc,
        "decisions": total,
        "supervised": (total > 0 and unsup == 0),
        "first_seen": lo.strftime("%H:%M:%S") if lo else None,
        "last_seen": hi.strftime("%H:%M:%S") if hi else None,
        "alive": bool(chain),
        "chain": chain,
    }


@app.get("/daemon")
def daemon_state():
    # Whether the daemon is alive, and what its risk window currently holds.
    # Absent file or a stale heartbeat both mean stopped -- which is worth
    # showing plainly, because Aegis fails open: with the daemon gone, files
    # that would be refused are simply opened and nothing is recorded.
    try:
        with open(STATUS_FILE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {"running": False, "reason": "no status file", "agents": []}

    age = time.time() - state.get("at", 0)
    if age > STATUS_STALE_AFTER:
        return {"running": False, "reason": "heartbeat %.0fs old" % age,
                "agents": [], "watching": state.get("watching")}

    state["running"] = True
    state["age"] = age
    return state


@app.get("/run")
def run_state():
    # The dashboard polls this so its status line cannot go stale. Without it
    # the browser has no way to tell a finished agent from a running one, and
    # the status would keep claiming "running" long after the agent exited.
    #
    # poll() also reaps the child, so calling it on a schedule stops finished
    # agents lingering as zombies.
    with _running_lock:
        if _running is None:
            return {"running": False}
        code = _running.poll()
        if code is None:
            return {"running": True, "pid": _running.pid}
        return {"running": False, "pid": _running.pid, "exit": code}


@app.get("/")
def dashboard():
    return FileResponse("dashboard.html")