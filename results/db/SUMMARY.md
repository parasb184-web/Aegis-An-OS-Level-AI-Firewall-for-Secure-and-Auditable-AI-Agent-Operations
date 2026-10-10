# DB module results (branch kushagra/db-fixes)

All numbers below come from commands run on 2026-10-10. Raw output is in
the `task*.txt` files next to this one; the scripts that produced them are
in `sql/` and `results/db/scripts/`.

## Read this first: dataset and machine

* **Regenerated synthetic dataset.** The 2M-row audit log from the earlier
  experiment was not in this database (it had 45 real rows, 5 policy rules,
  and no `idx_actions_ts`). All large-table numbers here are on
  `actions_exp`, a scratch table with the same columns and types as
  `actions` (checked in `sql/index_experiment_v2.sql`, 0 differing
  columns), filled by `sql/generate_dataset.sql`: 2,000,000 deterministic
  rows spanning the 7 days up to generation time, 1,800 distinct paths,
  90% allow / 5% block / 5% warn, 253 MB.
* **Machine.** Intel Core i5-10300H @ 2.50GHz, 8 logical CPUs. WSL2 was
  given 3.7 GiB RAM (default half of the host's 7.84 GB, no `.wslconfig`)
  and 1 GiB swap. Kernel 6.18.40.1-microsoft-standard-WSL2, PostgreSQL
  18.6, default settings (shared_buffers 128MB, work_mem 4MB,
  maintenance_work_mem 64MB, 2 parallel workers per gather).
* **Not comparable to the old result.** The original 186 ms -> 0.082 ms
  index result came from a different machine and dataset, was a single
  run, and its output was not saved. The numbers here should not be
  compared with it directly. Also, the path the old experiment looked up
  (`dir7/file123.txt`) cannot exist in that generator's data (dir needs
  i mod 100 = 7, file needs i mod 100 = 23), so it timed a lookup that
  returned 0 rows.
* **Method.** Each query/insert runs 6 times; run 1 (cold cache) is
  dropped and the median of runs 2-6 is reported, with min and max.
  Medians are computed by `results/db/scripts/medians.py`.

## Task 1: rule priority (`task1_rule_order.txt`)

`load_policies()` now uses `ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id`.
Bug reproduced first: after a no-op `UPDATE policies SET note = note WHERE id IN (1,2,3,4)`
the heap order became 5,1,2,3,4 and the old code returned
`~/demo/project/.env -> allow`. With the fix, same table:
`.env -> block`, `src/app.py -> allow`.

## Task 2: drift cleanup (`task2_cleanup.txt`)

`sql/cleanup.sql` deletes `'%/.ssh/%'` by pattern. On this machine the
row was already absent: `DELETE 0`, and `python3 db.py` prints
`loaded 5 rules`, matching schema.sql.

## Task 3: verdict_counts + trigger (`task3_trigger.txt`)

* Fresh setup from schema.sql (in a throwaway schema, rolled back): trigger
  counts match `GROUP BY` exactly, and an unseen verdict (`review`) gets
  its own row.
* Migration on the live db: counts 19 allow / 26 block / 0 warn, equal to
  `GROUP BY`.
* Atomicity: 3 inserts inside a transaction raised counts to 20/27/1;
  after `ROLLBACK` they were back to 19/26/0.
* Concurrency: while session A held an uncommitted `allow` insert, session
  B's `block` insert took 1.417 ms but its `allow` insert waited
  2496.761 ms (`ShareLock` on A's `transactionid`) until A finished.
* `curl localhost:8765/counts` -> `{"allow":19,"block":26,"warn":0}`.

## Task 4: index experiment v2 (`task4_*.txt`)

Command: `bash results/db/scripts/run_task4.sh`

| query | before (ms) | after (ms) | plan |
|---|---|---|---|
| (a) last 10 min, ORDER BY ts DESC LIMIT 50 | 94.625 (81.8-99.7) | 0.037 (0.036-0.038) | Parallel Seq Scan + top-N sort -> Index Scan on idx_exp_ts |
| (b) path hit, 1,111 rows | 191.558 (66.3-235.0) | 1.014 (0.911-1.126) | Parallel Seq Scan -> Bitmap Heap Scan |
| (b0) old path, 0 rows | 218.967 (83.7-335.3) | 0.013 (0.010-0.016) | same as (b) |
| (c) old /counts: GROUP BY verdict | 601.458 (277.1-772.8) | 197.417 (186.9-248.4) | **same plan both times** (Parallel Seq Scan) |
| (c) new /counts: verdict_counts | 0.008 (0.007-0.009) | - | Seq Scan on a 3-row table |

* (c) before vs after is noise and caching, not the indexes: the plan is
  identical and the spread is large because the 253 MB table does not fit
  in 128 MB of shared_buffers (each run reads about 16.4k blocks from
  outside it). The real fix for /counts is the summary table:
  hundreds of ms -> 0.008 ms.
* (b) after: `Heap Blocks: exact=1111`. Each matching row is on a
  different page, so most of the 1 ms is fetching scattered pages.
* Index builds on 2M rows, default maintenance_work_mem 64MB:
  `idx_exp_ts` 1040.834 ms (43 MB), `idx_exp_path` 2979.711 ms (14 MB).
  `vmstat` during the run: lowest free memory 1268 MB, swap used 0.
  The out-of-memory failure did not happen on this machine.
* `CREATE INDEX idx_actions_path ON actions (path)` on the live table:
  **succeeded**, 2.520 ms, but that table has 45 rows, so this only shows
  the statement works (`task4_live_path_index.txt`).

## Task 5: trigger insert cost (`task5_*.txt`)

| test | trigger off (ms) | trigger on (ms) | overhead |
|---|---|---|---|
| 10,000 rows, one INSERT...SELECT, real `actions` | 59.063 | 787.902 (trigger itself 721.718) | 13.3x |
| 10,000 rows, one INSERT...SELECT, `actions_exp` (2M rows) | 72.422 | 818.346 (trigger itself 732.364) | 11.3x |
| 10,000 rows, writer.py pattern (one INSERT per row, commit every 50), `actions_exp` | 1659.5 | 1868.2 | +12.6%, 20.9 us/row |

Commands: `psql ... -f sql/trigger_cost.sql` (rolled back each run),
`python3 sql/insert_bench.py`.

Why the single big insert is so much worse: trigger time per row grows
with the number of rows in one transaction (`sql/trigger_scaling.sql`,
real actions table, rolled back):

| rows in one transaction | 50 | 1,000 | 5,000 | 10,000 | 20,000 |
|---|---|---|---|---|---|
| trigger time, median (ms) | 0.456 | 14.748 | 182.018 | 632.886 | 2286.151 |
| per row (us) | 9.1 | 14.7 | 36.4 | 63.3 | 114.3 |

This is consistent with every upsert creating a new version of one of
the same 3 counter rows, which cannot be cleaned up while the
transaction is open. We measured the scaling, not the mechanism itself.
At writer.py's batch size of 50 the cost is small.

**Found along the way:** `actions.parent_action` has a foreign key but no
index. Deleting 20 rows from the 2M-row table spent 3611.401 ms in the
FK check; with an index on `parent_action`, 0.636 ms
(`sql/fk_delete_check.sql`). The real `actions` table has the same
problem. Not changed in this PR; suggested as a follow-up.

## Task 6: LISTEN/NOTIFY prototype (`task6_listen_notify.txt`)

A statement-level trigger on `policies` calls
`pg_notify('policies_changed', TG_OP)`; `sql/listen_demo.py` (37 lines)
listens and reloads. Command: `bash results/db/scripts/run_task6.sh`.
Rolled-back insert: no notification. Committed INSERT: `INSERT`, 6 rules.
Three UPDATEs in one transaction: one `UPDATE` notification. DELETE:
`DELETE`, back to 5 rules.

## Side effects on this database

* Rolled-back test inserts used up sequence values, so new `actions` ids
  will have a gap. Nothing depends on ids being gap-free.
* `actions_exp` (253 MB) and `verdict_counts_exp` are left in place for
  re-runs. Drop them with
  `DROP TABLE verdict_counts_exp; DROP TABLE actions_exp;`.
