# Fail-open test (current main)

A loop ran `cat ~/demo/.ssh/id_rsa` once per second (`tests/fp_fail_open.sh`). The policy rule `/home/%/.ssh/%` is `block`, so while the daemon is alive the open must fail with `Operation not permitted`. After the daemon is killed, the question is whether the kernel keeps denying or starts allowing (fail-open).

Times below are the loop's `date` stamps (local WSL clock). `actions.ts` is writer-thread insert time, about 2 seconds later, so it is only a cross-check.

Earlier attempts are not used as the labeled `kill -9` result: `sudo kill -9 1975` failed (`No such process`), and a later `sudo kill -9 $(pgrep …)` found no daemon. Those runs still flipped to `OPENED` after the daemon disappeared, but the stop method was not confirmed. Only the two runs below are counted.

## 1. `sudo kill -9` (confirmed)

- Daemon started and logged `marked 52 folders` / `loaded 5 policy rules` in `results/fp/raw/daemon_fail_open_kill9.log`.
- Loop: `results/fp/raw/fail_open_kill9.log`.
- `tests/fp_kill_daemon.sh` sent `kill -9` to PIDs **5677, 5680, 5682** (`sudo python3 -u daemon.py` and `python3 -u daemon.py`). The script printed `sent kill -9 to 5677 5680 5682`.
- The daemon log ends on a `DENY` line. There is no Python traceback (SIGKILL does not run cleanup).

| clock (WSL) | try | result |
|---|---:|---|
| 2026-10-10 09:38:18 | 1 | `FAILED` — Operation not permitted |
| 2026-10-10 09:38:52 | 34 | last `FAILED` |
| 2026-10-10 09:38:53 | 35 | first `OPENED` (8 bytes) |
| 2026-10-10 09:40:44 | 143 | last recorded `OPENED` |

34 denied opens, then every later open succeeded. After SIGKILL the kernel stopped asking Aegis and allowed the key file.

## 2. Ctrl+C (SIGINT)

- Daemon restarted into `results/fp/raw/daemon_fail_open_ctrlc.log` (`marked 52 folders`, `loaded 5 policy rules`).
- Loop: `results/fp/raw/fail_open_ctrlc.log` (this file is the second ctrlc attempt; the first attempt was only `FAILED` because Ctrl+C was pressed on the loop, not the daemon).
- Ctrl+C was pressed in the daemon window. That window returned to a shell prompt. The log ends on a `DENY` line; tee did not record a Python traceback.

| clock (WSL) | try | result |
|---|---:|---|
| 2026-10-10 09:44:01 | 1 | `FAILED` — Operation not permitted |
| 2026-10-10 09:44:37 | 36 | last `FAILED` |
| 2026-10-10 09:44:38 | 37 | first `OPENED` (8 bytes) |
| 2026-10-10 09:44:55 | 54 | last recorded `OPENED` |

Same fail-open as `kill -9`: one second after the daemon left, the key opened.

## Audit log cross-check

Query saved in `results/fp/raw/fail_open_db.txt`. For `path` matching `%/id_rsa` between `2026-10-10 09:38:00` and `09:46:00`:

- **94 `block` rows**, first `09:38:18.529901`, last `09:44:38.029967`
- **0 `allow` rows**

The `OPENED` attempts after each kill are not in `actions`. The daemon was already dead, so nothing recorded them. The 94 blocks cover the successful kill-9 run (34), the aborted first ctrlc loop (26), and the successful ctrlc run (36), minus a few rows the writer thread had not flushed when the process died (`FLUSH_SECONDS = 2`). `kill -9` and Ctrl+C both drop that in-memory queue.

## What this means

Aegis is a permission-event listener (`FAN_OPEN_PERM`). While it is running, Linux waits for allow or deny, and the `.ssh` rule denies. When the listener process is gone — SIGKILL or SIGINT — the kernel does not keep a stale deny. It fails open: the open proceeds. That avoids freezing every process under `~/demo` if the daemon crashes. It also means a crash or a kill is a protection gap: `id_rsa` becomes readable, and those opens leave no row in `actions`.
