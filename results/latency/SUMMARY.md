# Latency and audit-writer results

Branch `kashish/latency-and-writer`. Every number below came from a command
run on this machine on 2026-10-16; the commands are given with each result.
Raw per-open timings are in the `raw_*.csv` files next to this one.

## Machine

13th Gen Intel Core i5-13420H, 12 logical CPUs, 7.8 GiB RAM. Ubuntu under
WSL2, kernel 6.18.33.2-microsoft-standard-WSL2. Python 3.14.4,
PostgreSQL 18.6 with default settings.

Kushagra's database results were measured on a different machine
(i5-10300H, 8 CPUs), so the two sets of numbers are not comparable.

## Method

`bench/latency.py` times `os.open()` with `time.perf_counter_ns()`.
`os.open` is the raw syscall fanotify intercepts; Python's built-in `open()`
would add buffering setup and widen the interval.

`risk.py` blocks after `FILE_LIMIT = 15` opens inside `WINDOW = 10` s, so a
tight loop of 2000 opens would have timed denials rather than allow
decisions. The benchmark therefore opens in bursts of 10 (under the limit)
and sleeps 12 s between bursts (over the window), and records allowed and
blocked opens separately. No test-only override of `FILE_LIMIT` was added,
so there is nothing that could be left switched on by accident.

**Sample size.** 50 bursts x 10 opens = **500 opens per arm**, not the 2000
originally specified. Median and p95 are stable at this size; **p99 and max
rest on 5 and 1 samples respectively and should be read as indicative only.**

**First open of each burst is an outlier.** After a 12 s sleep the page
cache, the scheduler and the CPU's frequency state have all gone cold, so
the first open of every burst is far slower than the rest. That is an
artifact of the burst design, not of the daemon. The tables below give the
steady-state figures (opens 2-10) as the headline and the first-open
figures separately. The CSVs record `index_in_burst`, which is what makes
this split possible.

## Results: steady state (opens 2-10 of each burst, n=450)

All figures in microseconds.

| arm | median | p95 | p99 | max | overhead vs (a) |
|---|---:|---:|---:|---:|---:|
| (a) daemon off | 2.4 | 5.9 | 22.1 | 59.0 | - |
| (b) daemon on, unsupervised | 405.7 | 1271.1 | 1755.8 | 2069.0 | +403.3 |
| (c) daemon on, supervised | 405.0 | 1159.9 | 1887.0 | 3120.4 | +402.6 |

## Results: first open of each burst (n=50)

| arm | median | p95 | p99 | max |
|---|---:|---:|---:|---:|
| (a) daemon off | 43.9 | 209.9 | 652.5 | 652.5 |
| (b) daemon on, unsupervised | 839.4 | 1853.9 | 1956.0 | 1956.0 |
| (c) daemon on, supervised | 795.7 | 1530.3 | 2488.0 | 2488.0 |

All 500 opens were allowed in all three arms, so no denials contaminate the
timings (`BLOCKED opens: 0` in each run).

## What the numbers say

**Aegis costs about 403 microseconds per file open.** A process that opens
1000 files pays roughly 0.4 s of Aegis overhead on top of its own work.

**Policy and risk evaluation are free, within measurement error.** Arms (b)
and (c) differ by 0.7 us. Case (c) does strictly more work than (b): a
policy lookup against 5 rules, an ancestry walk through `/proc`,
`risk.record()` and `risk.score()`. Case (b) returns early with
`not supervised` and does none of it. The difference is noise.

So the cost is **interception, not decision-making**: the kernel freezing
the calling process, delivering the event, waiting for an answer and waking
the process again. Optimising the daemon's Python would not help. Reducing
this meaningfully would mean moving the decision into the kernel (eBPF) or
batching permission events.

That conclusion is supported by profiling the daemon's per-event userspace
work directly (2000 samples each, same machine):

| per-event work | median |
|---|---:|
| `parent_of()` - read `/proc/<pid>/stat` | 10.7 us |
| `name_of_process()` - read `/proc/comm` | 8.5 us |
| `path_of()` - readlink `/proc/self/fd` | 2.6 us |
| `refresh_roots()` - one `getmtime` | 1.9 us |
| `supervising_root()` cached hit | 0.1 us |
| `struct.pack` of the verdict | 0.2 us |
| `print()` to /dev/null | 0.3 us |
| **total** | **about 14 us** |

14 us of 403 us is 3.5%. The remaining 96.5% is the kernel round trip plus
terminal I/O, and **we did not separate those two.** See the open item below.

## Audit-writer results

| test | result |
|---|---|
| `stop()` drains 30 queued rows | 30/30 arrived, `stop()` returned in 0.028 s |
| Rows survive a failed shutdown flush | 5/5 arrived after one forced failure |
| SIGINT shutdown, writer holding 7 rows | exit code 0, 7/7 flushed, no traceback |
| SIGTERM shutdown, writer holding 7 rows | exit code 0, 7/7 flushed, no traceback |
| Ctrl+C on the running daemon | `stopping, flushing the audit log ... / stopped`, no traceback |
| **PostgreSQL stopped and restarted mid-run** | **40/40 rows survived** |

The outage run printed:

```
[writer] database error: SSL connection has been closed unexpectedly
[writer] waiting 3 s then reconnecting ...
[writer] reconnected and flushed 2 rows.
>>> clean stop: True
```

**Caveat on that test.** Only one error-and-reconnect cycle occurred and
only 2 rows were held at that moment, so this demonstrates recovery from a
dropped connection rather than a long outage with a large backlog. The
longer case was exercised separately by forcing `write_batch` to fail,
which is a simulation, not a real outage.

The audit log independently corroborates the benchmark: the daemon recorded
501 rows with reason `not supervised` during arm (b) and 500 with reason
`the agent workspace` during arm (c) - 500 opens in, 500 rows out, nothing
dropped across 1000 rows.

## How case (c) was run

`run_agent.sh` can only launch `fake_agent.py`, so there was no way to run
the benchmark under a registered root. It was registered by hand:

```bash
bash -c 'echo $$ >> /tmp/aegis_roots; exec python3 bench/latency.py \
    --target ~/demo/project/src/app.py --bursts 50 --label c_daemon_on_supervised'
```

The shell appends its own pid to the roots file and then `exec`s, which
replaces the shell without forking, so the registered pid is the pid the
benchmark runs under. Terminal output confirmed supervision was live: the
daemon's reason changed from `not supervised` to `the agent workspace`.

## Commands

```bash
# (a) daemon off
python3 bench/latency.py --target ~/demo/project/src/app.py --bursts 50 --label a_daemon_off

# daemon for (b) and (c)
sudo python3 daemon.py ~/demo --roots /tmp/aegis_roots

# (b) daemon on, unsupervised
python3 bench/latency.py --target ~/demo/project/src/app.py --bursts 50 --label b_daemon_on_unsupervised

# (c) daemon on, supervised - see above
```

## Open item: the print happens before the kernel is answered

In `daemon.py` the decision is printed to the terminal *before*
`answer(fan_fd, event_fd, verdict)`, despite the comment on the next line
saying the kernel is answered first. Every frozen process therefore waits
for a write to the terminal before it is released. Writing to a pty costs
far more than the 0.3 us measured against `/dev/null`, so this may be a
large share of the unexplained 390 us.

This was **not** fixed or measured in this PR. The test would be to re-run
arm (b) with the daemon's output redirected to a file and compare medians.
Logged as a follow-up.
