# Saves decisions to PostgreSQL without making the daemon wait.
#
# The process being checked is frozen while we decide, so we must answer the
# kernel as fast as possible. Writing to a database first would add that
# delay to every single file the agent opens.
#
# So: the daemon puts decisions on a queue (fast, in memory) and a separate
# thread takes them off and writes them to the database (slow, but nobody
# is waiting on it). Producer and consumer, with the queue in between.
#
# Reliability improvements in this version:
#   - write_batch + commit is wrapped in try/except. On error: rollback,
#     wait RETRY_WAIT seconds, reconnect, retry the same batch. The thread
#     never silently dies or drops rows while the database is down.
#   - stop() places a sentinel on the queue. writer_loop drains remaining
#     items, flushes the batch, commits, and exits. Call stop() + join()
#     from the daemon on SIGINT/SIGTERM (exact lines in PR description).
#   - Thread is daemon=False. daemon=True lets Python kill the thread
#     mid-flush -- the exact bug we are fixing. stop() gives it an orderly
#     exit path so we no longer need the OS to kill it for us.

import queue
import threading
import time

import db

# Sentinel: writer_loop exits cleanly when it dequeues this exact object.
_STOP = object()

_thread = None
decisions = queue.Queue()

BATCH_SIZE = 50
FLUSH_SECONDS = 2

# Seconds to wait after a DB error before reconnecting.
RETRY_WAIT = 3


def record(pid, process_name, path, verdict, reason):
    # Called by the daemon on every intercepted open. Must return immediately.
    decisions.put((pid, process_name, path, verdict, reason))


def write_batch(cur, batch):
    for pid, process_name, path, verdict, reason in batch:
        cur.execute(
            'INSERT INTO actions (pid, process_name, path, verdict, reason) '
            'VALUES (%s, %s, %s, %s, %s)',
            (pid, process_name, path, verdict, reason))


def writer_loop():
    conn = db.connect()
    cur = conn.cursor()
    batch = []
    last_flush = time.time()

    while True:
        try:
            # Block up to half a second waiting for work. The timeout lets us
            # flush on schedule even during quiet periods.
            item = decisions.get(timeout=0.5)
        except queue.Empty:
            item = None

        if item is _STOP:
            # Orderly shutdown requested. Flush remaining rows, then exit.
            # We do NOT put _STOP back -- one stop() shuts down one thread.
            if batch:
                try:
                    write_batch(cur, batch)
                    conn.commit()
                except Exception as e:
                    print('[writer] error during shutdown flush: ' + str(e))
                    try:
                        conn.rollback()
                    except Exception:
                        pass
            return

        if item is not None:
            batch.append(item)

        old_enough = time.time() - last_flush > FLUSH_SECONDS
        if not batch or not (len(batch) >= BATCH_SIZE or old_enough):
            continue

        # Attempt to write the batch. On any database error: rollback so the
        # connection is not left in a failed transaction, wait briefly, then
        # reconnect and retry the same batch once. If the retry also fails,
        # keep the rows in memory -- the loop tries again on the next cycle.
        # We never clear the batch on failure.
        try:
            write_batch(cur, batch)
            conn.commit()
            batch = []
            last_flush = time.time()
        except Exception as e:
            print('[writer] database error: ' + str(e))
            try:
                conn.rollback()
            except Exception:
                pass

            print('[writer] waiting ' + str(RETRY_WAIT) + ' s then reconnecting ...')
            time.sleep(RETRY_WAIT)

            try:
                conn.close()
            except Exception:
                pass

            try:
                conn = db.connect()
                cur = conn.cursor()
                n = len(batch)
                write_batch(cur, batch)
                conn.commit()
                batch = []
                last_flush = time.time()
                print('[writer] reconnected and flushed ' + str(n) + ' rows.')
            except Exception as e2:
                print('[writer] retry failed: ' + str(e2))
                print('[writer] ' + str(len(batch)) + ' rows held in memory, will retry next cycle.')
                # Leave batch intact so the next flush attempt picks it up.


def start():
    # daemon=False: we want the thread to finish its final flush before the
    # process exits. The caller must call stop() to signal it.
    global _thread
    _thread = threading.Thread(target=writer_loop, daemon=False)
    _thread.start()
    return _thread


def stop():
    # Tell the writer thread to flush remaining rows and exit, then wait.
    # The daemon must call this on SIGINT/SIGTERM before sys.exit() so that
    # rows already on the queue are not lost.
    #
    # What this still cannot protect against: kill -9, OOM kill, or a power
    # cut. In those cases the queue is in memory and is gone. A write-ahead
    # log on disk would be needed to survive those scenarios.
    decisions.put(_STOP)
    if _thread is not None:
        _thread.join()


if __name__ == '__main__':
    start()
    record(1234, 'cat', '/home/test/normal.txt', 'allow', 'test row')
    record(1234, 'cat', '/home/test/secret.txt', 'block', 'test row')
    time.sleep(3)
    print('wrote 2 test rows')
