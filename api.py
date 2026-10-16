# Small web server that reads the audit log for the dashboard.
# It only reads. All the deciding happens in daemon.py.

import os
import subprocess
import threading

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


@app.get("/")
def dashboard():
    return FileResponse("dashboard.html")