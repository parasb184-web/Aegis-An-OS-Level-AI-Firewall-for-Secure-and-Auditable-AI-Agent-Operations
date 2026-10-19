import contextlib
import json
import os
import subprocess
import threading
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

import db

app = FastAPI()

SCENARIOS = ("normal", "credentials", "massread")

ROOTS_FILE = os.environ.get("AEGIS_ROOTS", "/tmp/aegis_roots")

STATUS_FILE = os.environ.get("AEGIS_STATUS", "/tmp/aegis_status.json")

STATUS_STALE_AFTER = 3.0

AEGIS_DIR = os.path.dirname(os.path.abspath(__file__))

_running = None
_running_lock = threading.Lock()


@app.get("/counts")
def counts():
    with cursor() as cur:
        cur.execute("SELECT verdict, n FROM verdict_counts")
        rows = cur.fetchall()

    result = {"allow": 0, "block": 0, "warn": 0}
    for verdict, count in rows:
        result[verdict] = count
    return result


@app.get("/recent")
def recent():
    with cursor() as cur:
        cur.execute(
            "SELECT ts, process_name, path, verdict, reason "
            "FROM actions ORDER BY id DESC LIMIT 50")
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
def run(scenario: str):
    if scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail="unknown scenario")

    global _running
    with _running_lock:
        if _running is not None and _running.poll() is None:
            return {"started": False, "reason": "already running"}

        try:
            proc = subprocess.Popen(
                ["python3", "fake_agent.py", scenario], cwd=AEGIS_DIR)
        except OSError as e:
            raise HTTPException(status_code=500, detail="could not start: %s" % e)

        try:
            with open(ROOTS_FILE, "a") as f:
                f.write("%d\n" % proc.pid)
        except OSError as e:
            proc.kill()
            raise HTTPException(status_code=500,
                                detail="could not register pid: %s" % e)

        _running = proc

    return {"started": True, "scenario": scenario, "pid": proc.pid}


@contextlib.contextmanager
def cursor():
    conn = db.connect()
    cur = conn.cursor()
    try:
        yield cur
    finally:
        cur.close()
        conn.close()


def rows_to_dicts(cur):
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

SYNTHETIC = "/home/%/demo/notes/dir%"
NOT_SYNTHETIC = "path NOT LIKE %s"


@app.get("/verdict/{verdict}")
def by_verdict(verdict: str):
    if verdict not in ("allow", "warn", "block"):
        raise HTTPException(status_code=400, detail="unknown verdict")

    with cursor() as cur:
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
    return {"verdict": verdict, "rows": rows,
            "top_files": top_files, "top_reasons": top_reasons}


@app.get("/sessions")
def sessions():
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
            ("%/.ssh/%", "%/notes/%", SYNTHETIC))

        out = []
        for (pid, proc, lo, hi, n, a, w, b, ssh, notes, unsup) in cur.fetchall():
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
    return out


@app.get("/session/{pid}")
def session(pid: int):
    with cursor() as cur:
        cur.execute("SELECT " + ROW_COLS + " FROM actions WHERE pid = %s AND "
                    + NOT_SYNTHETIC + " ORDER BY id", (pid, SYNTHETIC))
        rows = rows_to_dicts(cur)
    return {"pid": pid, "rows": rows}


@app.get("/rules")
def rules():
    with cursor() as cur:
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

        out_other = [{"reason": r, "n": n} for r, n in fired.items()
                     if r not in [x["note"] for x in out]]
    return {"rules": out, "other": sorted(out_other, key=lambda x: -x["n"])}


@app.get("/history")
def history(path: str):
    with cursor() as cur:
        cur.execute("SELECT " + ROW_COLS + " FROM actions WHERE path = %s "
                    "ORDER BY id DESC LIMIT 200", (path,))
        rows = rows_to_dicts(cur)
    return {"path": path, "rows": rows}


@app.get("/process/{pid}")
def process(pid: int):
    with cursor() as cur:
        cur.execute("SELECT count(*), count(*) FILTER (WHERE reason='not supervised'),"
                    "       min(process_name), min(ts), max(ts) "
                    "FROM actions WHERE pid = %s AND " + NOT_SYNTHETIC, (pid, SYNTHETIC))
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
def daemon_state():
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
