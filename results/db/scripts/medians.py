# Reads the raw output of sql/index_experiment_v2.sql (or the insert
# benchmark) and prints, for each label, the median execution time of
# runs 2..N. Run 1 is dropped because it is the cold-cache run.
#
#   python3 results/db/scripts/medians.py results/db/task4_explain_raw.txt

import re
import statistics
import sys

times = {}
trigger_times = {}
plans = {}
label = None
run = None
first_plan_line = False

for line in open(sys.argv[1]):
    m = re.match(r"=== (\S+) run (\d+)", line)
    if m:
        label, run = m.group(1), int(m.group(2))
        times.setdefault(label, [])
        first_plan_line = True
        continue
    if label is None:
        continue
    # The first line after the header row and dashes is the top plan node.
    if first_plan_line and "(cost=" in line:
        plans[label] = line.strip().split("  (cost=")[0]
        first_plan_line = False
    m = re.search(r"Execution Time: ([\d.]+) ms", line)
    if m and run > 1:
        times[label].append(float(m.group(1)))
    # EXPLAIN ANALYZE on an INSERT also reports time spent in triggers.
    m = re.search(r"Trigger (\S+): time=([\d.]+)", line)
    if m and run > 1 and not m.group(1).startswith("RI_"):
        trigger_times.setdefault(label, []).append(float(m.group(2)))

print("%-22s %10s %10s %10s  %s" % ("label", "median_ms", "min_ms", "max_ms", "top plan node"))
for label in times:
    t = times[label]
    if not t:
        continue
    print("%-22s %10.3f %10.3f %10.3f  %s" % (
        label, statistics.median(t), min(t), max(t), plans.get(label, "")))
    print("%-22s runs 2-%d: %s" % ("", len(t) + 1, ", ".join("%.3f" % x for x in t)))
    if label in trigger_times:
        print("%-22s of which trigger, median: %.3f ms" % (
            "", statistics.median(trigger_times[label])))
