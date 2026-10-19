import queue
import threading
import time

import db

_STOP = object()

_thread = None
decisions = queue.Queue()

BATCH_SIZE = 50
FLUSH_SECONDS = 2

RETRY_WAIT = 3

STOP_TIMEOUT = 10


def record(pid, process_name, path, verdict, reason):
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
            item = decisions.get(timeout=0.5)
        except queue.Empty:
            item = None

        if item is _STOP:
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

                    try:
                        conn.close()
                    except Exception:
                        pass
                    try:
                        conn = db.connect()
                        cur = conn.cursor()
                        write_batch(cur, batch)
                        conn.commit()
                        print('[writer] shutdown flush succeeded after reconnect.')
                    except Exception as e2:
                        print('[writer] shutdown flush failed again: ' + str(e2))
                        print('[writer] ' + str(len(batch)) + ' rows lost.')
            return

        if item is not None:
            batch.append(item)

        old_enough = time.time() - last_flush > FLUSH_SECONDS
        if not batch or not (len(batch) >= BATCH_SIZE or old_enough):
            continue

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


def start():
    global _thread
    _thread = threading.Thread(target=writer_loop, daemon=False)
    _thread.start()
    return _thread


def stop(timeout=STOP_TIMEOUT):
    decisions.put(_STOP)
    if _thread is None:
        return True
    _thread.join(timeout)
    if _thread.is_alive():
        print('[writer] did not finish within ' + str(timeout) + ' s.')
        return False
    return True


if __name__ == '__main__':
    start()
    record(1234, 'cat', '/home/test/normal.txt', 'allow', 'test row')
    record(1234, 'cat', '/home/test/secret.txt', 'block', 'test row')
    time.sleep(3)
    print('wrote 2 test rows')
