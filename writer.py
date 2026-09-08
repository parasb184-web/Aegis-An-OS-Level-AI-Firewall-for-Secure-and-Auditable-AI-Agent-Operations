# Saves decisions to PostgreSQL without making the daemon wait.
#
# The process being checked is frozen while we decide, so we must answer the
# kernel as fast as possible. Writing to a database first would add that
# delay to every single file the agent opens.
#
# So: the daemon puts decisions on a queue (fast, in memory) and a separate
# thread takes them off and writes them to the database (slow, but nobody
# is waiting on it). Producer and consumer, with the queue in between.

import queue
import threading
import time

import db

decisions = queue.Queue()

BATCH_SIZE = 50
FLUSH_SECONDS = 2


def record(pid, process_name, path, verdict, reason):
    # Called by the daemon. Must return immediately.
    decisions.put((pid, process_name, path, verdict, reason))


def write_batch(cur, batch):
    for pid, process_name, path, verdict, reason in batch:
        cur.execute(
            "INSERT INTO actions (pid, process_name, path, verdict, reason) "
            "VALUES (%s, %s, %s, %s, %s)",
            (pid, process_name, path, verdict, reason))


def writer_loop():
    conn = db.connect()
    cur = conn.cursor()
    batch = []
    last_flush = time.time()

    while True:
        try:
            # Wait up to half a second for something to arrive. The timeout
            # is what lets us flush on time even when traffic is slow.
            item = decisions.get(timeout=0.5)
            batch.append(item)
        except queue.Empty:
            pass

        old_enough = time.time() - last_flush > FLUSH_SECONDS
        if batch and (len(batch) >= BATCH_SIZE or old_enough):
            write_batch(cur, batch)
            conn.commit()
            batch = []
            last_flush = time.time()


def start():
    # daemon=True so this thread dies with the main program instead of
    # keeping it alive at shutdown.
    t = threading.Thread(target=writer_loop, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    start()
    record(1234, "cat", "/home/test/normal.txt", "allow", "test row")
    record(1234, "cat", "/home/test/secret.txt", "block", "test row")
    time.sleep(3)
    print("wrote 2 test rows")