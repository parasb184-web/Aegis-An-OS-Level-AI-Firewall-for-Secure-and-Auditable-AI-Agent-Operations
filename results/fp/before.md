# False-positive test: before (current main)

Measured on 2026-10-10 against `main` at `8cdea97`, before any agent-identification work. The daemon does not identify the process: every open under `~/demo` shares one 10-second risk window (`FILE_LIMIT = 15`, `FOLDER_LIMIT = 4`, `BLOCK_AT = 40`). Only the daemon's own PID is skipped.

**Repo:** pallets/click `@ 8.1.7` (`874ca2bc1c30d93a4ac6e36a15ed685eafe89097`) at `/home/mansi/demo/project/realrepo`. 146 files excluding `.git`, 174 including `.git`, 41 folders inside the clone. Daemon marked 52 folders under `~/demo` and loaded 5 policy rules. pytest 9.0.2.

**How:** `PGPASSWORD=… bash tests/fp_run.sh before wait` then `… before nowait`. Each command's opens are counted from `actions` **by PID**, not by `actions.ts` (that timestamp is the writer-thread insert time). Raw files: `results/fp/raw/before_wait/` and `results/fp/raw/before_nowait/`. Block rows: `blocks.csv` in each folder.

**Failed** means a non-zero exit status. `find` and `ls` created no fanotify file-open events (`FAN_ONDIR` is not set), so they are controls: they can succeed even while the risk window is full.

The console line `fatal: not a git repository` during script startup came from the metadata `git` calls (stdout-only redirect) before the 15 s settle. It is not a measured command result. `git status` / `git log` errors below are from the command stderr files.

## Wait run (15 s between commands)

Window: `db_start 2026-10-10 09:19:20.779873` to `db_end 2026-10-10 09:20:44.794941`. 600 block rows, all from the three failing commands (`420 + 160 + 20`).

| command | blocked opens | total opens | did the command fail? |
|---|---:|---:|---|
| `git status` | 420 | 435 | yes (exit 128) |
| `git log -5` | 0 | 8 | no (exit 0) |
| `grep -r "import" .` | 160 | 175 | yes (exit 2) |
| `find . -name "*.py"` | 0 | 0 | no (exit 0) |
| `ls -R` | 0 | 0 | no (exit 0) |
| `python3 -m pytest --collect-only` | 20 | 35 | yes (exit 2) |

First block of each failing command (from `first_block.txt`):

- `git` pid 2051: `risk 70: 16 files in 10s, 5 folders` on `.github/workflows/tests.yaml`
- `grep` pid 2078: `risk 40: 16 files in 10s` on `src/click/utils.py`
- `python3` pid 2120: `risk 40: 16 files in 10s` on `tests/test_arguments.py`

`git status` stderr: `unable to access '.git/info/exclude': Operation not permitted`. `git log -5` printed the five commits and opened only 8 files, so it stayed under the limit. `grep` printed 160 `Operation not permitted` lines. pytest: 20 collection `PermissionError`s, then `Interrupted: 20 errors during collection`.

## No-wait run (commands back to back)

Window: `db_start 2026-10-10 09:21:35.865584` to `db_end 2026-10-10 09:21:43.839044`. 596 block rows.

| command | blocked opens | total opens | did the command fail? |
|---|---:|---:|---|
| `git status` | 419 | 434 | yes (exit 128) |
| `git log -5` | 1 | 1 | yes (exit 128) |
| `grep -r "import" .` | 175 | 175 | yes (exit 2) |
| `find . -name "*.py"` | 0 | 0 | no (exit 0) |
| `ls -R` | 0 | 0 | no (exit 0) |
| `python3 -m pytest --collect-only` | 1 | 1 | yes (exit 1) |

First block reasons:

- `git` pid 2217: `risk 70: 16 files in 10s, 5 folders` (same trip as the wait run)
- `git` pid 2226 (`git log`): `risk 70: 435 files in 10s, 26 folders` on `.git/HEAD`
- `grep` pid 2235: `risk 70: 436 files in 10s, 26 folders` — every open denied
- `python3` pid 2262: `risk 70: 611 files in 10s, 33 folders` on `tox.ini`

`git log` stderr: `fatal: not a git repository (or any of the parent directories): .git` — it could not open `.git/HEAD`. pytest never reached collection; it died opening `tox.ini` (`PermissionError`).

## Why the two runs differ

The risk window is one shared list of the last 10 seconds of opens. In the wait run, 15 s of idle time lets that list empty, so each command starts from zero. `git log` only needs 8 opens, so it is allowed. `git status`, `grep`, and pytest each cross 15 opens on their own and then fail.

In the no-wait run, `git status` leaves hundreds of opens in the window. The next commands start already over the limit, so `git log` is denied on its first file and grep is denied on every file. `find` and `ls` still succeed because they never open files, so the daemon never sees them.
