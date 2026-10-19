import argparse
import csv
import os
import statistics
import sys
import time

BURST_SIZE = 10
BURST_PAUSE = 12.0


def parse_args():
    p = argparse.ArgumentParser(
        description='Time file opens with and without the Aegis daemon.')
    p.add_argument('--target', required=True,
                   help='File to open. Must already exist.')
    p.add_argument('--bursts', type=int, default=50,
                   help='Number of bursts. Default 50 gives 500 opens total.')
    p.add_argument('--out', default=None,
                   help='CSV path. Defaults to results/latency/raw_<label>.csv')
    p.add_argument('--label', default=None,
                   help='Short label for filenames and headers.')
    return p.parse_args()


def open_and_time(path):
    t0 = time.perf_counter_ns()
    try:
        fd = os.open(path, os.O_RDONLY)
        t1 = time.perf_counter_ns()
        os.close(fd)
        return t1 - t0, 'allowed'
    except PermissionError:
        t1 = time.perf_counter_ns()
        return t1 - t0, 'blocked'
    except OSError as e:
        print('ERROR opening ' + path + ': ' + str(e), file=sys.stderr)
        sys.exit(1)


def ns_to_us(ns):
    return ns / 1000.0


def percentile(sorted_data, pct):
    if not sorted_data:
        return float('nan')
    idx = min(int(len(sorted_data) * pct / 100), len(sorted_data) - 1)
    return sorted_data[idx]


def summarise(times_ns):
    if not times_ns:
        print('    no data')
        return
    us = sorted(ns_to_us(x) for x in times_ns)
    print('    count  : ' + str(len(us)))
    print('    median : %.1f us' % statistics.median(us))
    print('    p95    : %.1f us' % percentile(us, 95))
    print('    p99    : %.1f us' % percentile(us, 99))
    print('    max    : %.1f us' % max(us))


def main():
    args = parse_args()

    target = os.path.expanduser(args.target)
    if not os.path.exists(target):
        print('Target file does not exist: ' + target, file=sys.stderr)
        print('Create it first:  touch ' + target, file=sys.stderr)
        sys.exit(1)

    label = args.label or os.path.basename(target).replace('.', '_')

    out_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'results', 'latency')
    os.makedirs(out_dir, exist_ok=True)
    out_path = args.out or os.path.join(out_dir, 'raw_' + label + '.csv')

    total_opens = args.bursts * BURST_SIZE
    print('Aegis latency benchmark')
    print('  target  : ' + target)
    print('  bursts  : %d x %d opens = %d total' % (args.bursts, BURST_SIZE, total_opens))
    print('  pause   : %d s between bursts (> WINDOW=10s in risk.py)' % int(BURST_PAUSE))
    print('  output  : ' + out_path)
    print()

    allowed_ns = []
    blocked_ns = []
    rows = []

    for burst in range(args.bursts):
        if burst > 0:
            sys.stdout.write('  burst %d/%d done -- sleeping %d s ...  \r' % (
                burst, args.bursts, int(BURST_PAUSE)))
            sys.stdout.flush()
            time.sleep(BURST_PAUSE)

        for i in range(BURST_SIZE):
            elapsed_ns, verdict = open_and_time(target)
            rows.append((burst, i, elapsed_ns, verdict))
            if verdict == 'allowed':
                allowed_ns.append(elapsed_ns)
            else:
                blocked_ns.append(elapsed_ns)

    print()
    print('Results')
    print('  ALLOWED opens (%d):' % len(allowed_ns))
    summarise(allowed_ns)

    if blocked_ns:
        print()
        print('  BLOCKED opens (%d) -- NOT included in allowed stats:' % len(blocked_ns))
        summarise(blocked_ns)
    else:
        print('  BLOCKED opens: 0  (risk window stayed clean)')

    with open(out_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['burst', 'index_in_burst', 'elapsed_ns', 'verdict'])
        w.writerows(rows)
    print()
    print('Raw data saved to: ' + out_path)


if __name__ == '__main__':
    main()
