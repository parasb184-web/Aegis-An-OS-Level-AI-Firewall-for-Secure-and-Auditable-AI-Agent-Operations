"""Aegis REST API and Dashboard Server.

Provides telemetry endpoints for dashboard rendering, process inspection,
verdict aggregation, scenario invocation, and daemon heartbeat status.
"""

import contextlib
import json
import os
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import db

app = FastAPI(title="Aegis AI Firewall API", version="1.0.0")

# Supported agent test scenarios
SCENARIOS = ("normal", "credentials", "massread")

# File where active agent root PIDs are written
ROOTS_FILE: str = os.environ.get("AEGIS_ROOTS", "/tmp/aegis_roots")

# File where daemon writes status heartbeats
STATUS_FILE: str = os.environ.get("AEGIS_STATUS", "/tmp/aegis_status.json")

# Heartbeat timeout before marking daemon as stopped
STATUS_STALE_AFTER: float = 3.0

AEGIS_DIR: str = os.path.dirname(os.path.abspath(__file__))

# Lock and process handle for active demo scenarios
_running: Optional[subprocess.Popen] = None
_running_lock = threading.Lock()


@contextlib.contextmanager
def cursor():
    """Context manager yielding a PostgreSQL cursor with automatic closure."""
    conn = db.connect()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
        conn.close()


def rows_to_dicts(cur) -> List[Dict[str, Any]]:
    """Convert cursor action rows to standard dictionary format."""
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

# Synthetic test pattern filter to exclude artificial benchmark paths
SYNTHETIC = "/home/%/demo/notes/dir%"
NOT_SYNTHETIC = "path NOT LIKE %s"


@app.get("/counts")
def counts() -> Dict[str, int]:
    """Retrieve aggregate decision counts (allow, warn, block) from verdict_counts."""
    with cursor() as cur:
        cur.execute("SELECT verdict, n FROM verdict_counts")
        rows = cur.fetchall()

    result = {"allow": 0, "block": 0, "warn": 0}
    for verdict, count in rows:
        result[verdict] = count
    return result


@app.get("/recent")
def recent() -> List[Dict[str, Any]]:
    """Retrieve the 50 most recent security decisions for the live audit feed."""
    with cursor() as cur:
        cur.execute(
            "SELECT ts, process_name, path, verdict, reason "
            "FROM actions ORDER BY id DESC LIMIT 50"
        )
        rows = cur.fetchall()

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
def run(scenario: str) -> Dict[str, Any]:
    """Launch a scripted test agent scenario and register its PID with the daemon."""
    if scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail="unknown scenario")

    global _running
    with _running_lock:
        if _running is not None and _running.poll() is None:
            return {"started": False, "reason": "already running"}

        try:
            proc = subprocess.Popen(
                ["python3", "fake_agent.py", scenario], cwd=AEGIS_DIR
            )
        except OSError as e:
            raise HTTPException(status_code=500, detail="could not start: %s" % e)

        try:
            with open(ROOTS_FILE, "a") as f:
                f.write("%d\n" % proc.pid)
        except OSError as e:
            proc.kill()
            raise HTTPException(
                status_code=500, detail="could not register pid: %s" % e
            )

        _running = proc

    return {"started": True, "scenario": scenario, "pid": proc.pid}


@app.get("/verdict/{verdict}")
def by_verdict(verdict: str) -> Dict[str, Any]:
    """Drill down into decisions for a specific verdict with top files and reasons."""
    if verdict not in ("allow", "warn", "block"):
        raise HTTPException(status_code=400, detail="unknown verdict")

    with cursor() as cur:
        cur.execute(
            "SELECT " + ROW_COLS + " FROM actions WHERE verdict = %s AND "
            + NOT_SYNTHETIC + " ORDER BY id DESC LIMIT 100",
            (verdict, SYNTHETIC),
        )
        rows = rows_to_dicts(cur)

        cur.execute(
            "SELECT path, count(*) FROM actions WHERE verdict = %s AND "
            + NOT_SYNTHETIC + " GROUP BY path ORDER BY 2 DESC LIMIT 5",
            (verdict, SYNTHETIC),
        )
        top_files = [{"path": p, "n": n} for p, n in cur.fetchall()]

        cur.execute(
            "SELECT reason, count(*) FROM actions WHERE verdict = %s AND "
            + NOT_SYNTHETIC + " GROUP BY reason ORDER BY 2 DESC LIMIT 5",
            (verdict, SYNTHETIC),
        )
        top_reasons = [{"reason": r, "n": n} for r, n in cur.fetchall()]

    return {
        "verdict": verdict,
        "rows": rows,
        "top_files": top_files,
        "top_reasons": top_reasons,
    }


@app.get("/sessions")
def sessions() -> List[Dict[str, Any]]:
    """Retrieve historical agent execution sessions grouped by process tree PID."""
    with cursor() as cur:
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
            ("%/.ssh/%", "%/notes/%", SYNTHETIC),
        )

        out = []
        for pid, proc, lo, hi, n, a, w, b, ssh, notes, unsup in cur.fetchall():
            if notes:
                scenario = "massread"
            elif ssh:
                scenario = "credentials"
            elif n <= 5:
                scenario = "normal"
            else:
                scenario = "unknown"
            out.append({
                "pid": pid,
                "process": proc,
                "scenario": scenario,
                "started": lo.strftime("%H:%M:%S"),
                "ended": hi.strftime("%H:%M:%S"),
                "total": n,
                "allow": a,
                "warn": w,
                "block": b,
                "supervised": unsup == 0,
            })
    return out


@app.get("/session/{pid}")
def session(pid: int) -> Dict[str, Any]:
    """Retrieve chronological decision sequence for a specific session PID."""
    with cursor() as cur:
        cur.execute(
            "SELECT " + ROW_COLS + " FROM actions WHERE pid = %s AND "
            + NOT_SYNTHETIC + " ORDER BY id",
            (pid, SYNTHETIC),
        )
        rows = rows_to_dicts(cur)
    return {"pid": pid, "rows": rows}


@app.get("/rules")
def rules() -> Dict[str, Any]:
    """Retrieve active policy rules with real-time trigger frequencies."""
    with cursor() as cur:
        cur.execute(
            "SELECT id, path_pattern, sensitivity, action, note "
            "FROM policies ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id"
        )
        rule_rows = cur.fetchall()

        cur.execute(
            "SELECT reason, count(*) FROM actions WHERE " + NOT_SYNTHETIC +
            " GROUP BY reason",
            (SYNTHETIC,),
        )
        fired = dict(cur.fetchall())

        out = []
        for rid, pattern, sens, action, note in rule_rows:
            out.append({
                "id": rid,
                "pattern": pattern,
                "sensitivity": sens,
                "action": action,
                "note": note,
                "fired": fired.get(note, 0),
            })

        out_other = [
            {"reason": r, "n": n}
            for r, n in fired.items()
            if r not in [x["note"] for x in out]
        ]
    return {"rules": out, "other": sorted(out_other, key=lambda x: -x["n"])}


@app.get("/history")
def history(path: str) -> Dict[str, Any]:
    """Inspect all decisions recorded for a specific target filesystem path."""
    with cursor() as cur:
        cur.execute(
            "SELECT " + ROW_COLS + " FROM actions WHERE path = %s "
            "ORDER BY id DESC LIMIT 200",
            (path,),
        )
        rows = rows_to_dicts(cur)
    return {"path": path, "rows": rows}


@app.get("/process/{pid}")
def process(pid: int) -> Dict[str, Any]:
    """Inspect process details and traverse /proc parent process tree."""
    with cursor() as cur:
        cur.execute(
            "SELECT count(*), count(*) FILTER (WHERE reason='not supervised'),"
            "       min(process_name), min(ts), max(ts) "
            "FROM actions WHERE pid = %s AND " + NOT_SYNTHETIC,
            (pid, SYNTHETIC),
        )
        total, unsup, proc, lo, hi = cur.fetchone()

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
            break
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
def daemon_state() -> Dict[str, Any]:
    """Query heartbeat status and supervised agent list from daemon status file."""
    try:
        with open(STATUS_FILE) as f:
            state = json.load(f)
    except (OSError, ValueError):
        return {"running": False, "reason": "no status file", "agents": []}

    age = time.time() - state.get("at", 0)
    if age > STATUS_STALE_AFTER:
        return {
            "running": False,
            "reason": "heartbeat %.0fs old" % age,
            "agents": [],
            "watching": state.get("watching"),
        }

    state["running"] = True
    state["age"] = age
    return state


@app.get("/run")
def run_state() -> Dict[str, Any]:
    """Check running state and PID of currently active scenario subprocess."""
    with _running_lock:
        if _running is None:
            return {"running": False}
        code = _running.poll()
        if code is None:
            return {"running": True, "pid": _running.pid}
        return {"running": False, "pid": _running.pid, "exit": code}


@app.get("/")
def dashboard():
    """Serve the primary Aegis Security Operations Dashboard HTML page."""
    return FileResponse("dashboard.html")
