# Aegis daemon.
#
# Sits between a process and the files it opens. Linux pauses the open and
# asks us; we check the rules and answer allow or deny. Every decision is
# recorded, but only AFTER we have answered, so the paused process is not
# waiting on a database write.

import ctypes
import os
import struct
import sys
import time
import risk
import db
import writer

libc = ctypes.CDLL("libc.so.6", use_errno=True)

FAN_CLOEXEC        = 0x00000001
FAN_CLASS_CONTENT  = 0x00000004
FAN_OPEN_PERM      = 0x00010000
FAN_EVENT_ON_CHILD = 0x08000000
FAN_MARK_ADD       = 0x00000001
FAN_ALLOW          = 0x01
FAN_DENY           = 0x02

AT_FDCWD = -100
O_RDONLY = 0

# Where run_agent.sh and the dashboard register the agent they just started.
DEFAULT_ROOTS = "/tmp/aegis_roots"

# How often we re-read that file and forget processes that have exited.
# Doing it per open would cost a stat for every cached pid; once a second
# is often enough and keeps the work off the hot path.
SWEEP_SECONDS = 1.0

# A parent chain this long means something is wrong; stop rather than spin.
MAX_DEPTH = 40

EVENT_FORMAT = "<IBBHQii"

libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
libc.fanotify_mark.argtypes = [ctypes.c_int, ctypes.c_uint, ctypes.c_uint64,
                               ctypes.c_int, ctypes.c_char_p]


def start_fanotify():
    fan_fd = libc.fanotify_init(FAN_CLOEXEC | FAN_CLASS_CONTENT, O_RDONLY)
    if fan_fd < 0:
        err = ctypes.get_errno()
        print("fanotify_init failed:", os.strerror(err))
        if err == 1:
            print("-> Run this with sudo.")
        if err == 22:
            print("-> This kernel has no permission event support.")
        sys.exit(1)
    return fan_fd


def watch_folder(fan_fd, folder):
    result = libc.fanotify_mark(fan_fd, FAN_MARK_ADD,
                                FAN_OPEN_PERM | FAN_EVENT_ON_CHILD,
                                AT_FDCWD, folder.encode())
    if result < 0:
        print("fanotify_mark failed:", os.strerror(ctypes.get_errno()))
        sys.exit(1)


def path_of(fd):
    try:
        return os.readlink("/proc/self/fd/%d" % fd)
    except OSError:
        return "<unknown>"


def name_of_process(pid):
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip()
    except OSError:
        return "<gone>"


# Which processes are the agent.
#
# We are told the pid of one process (the root) and we supervise it and
# everything it starts. For each open we walk up the parent chain: reach a
# root and this is the agent, reach init first and it is somebody else.

roots = set()            # pids we supervise, plus everything beneath them
supervised_cache = {}    # pid -> the root supervising it, or None
last_sweep = 0.0


def parent_of(pid):
    # The 4th field of /proc/<pid>/stat is the parent pid. The 2nd field is
    # the program name in brackets and it can itself contain spaces and
    # brackets, so we count fields from the LAST closing bracket instead of
    # splitting the whole line.
    try:
        with open("/proc/%d/stat" % pid) as f:
            line = f.read()
    except OSError:
        return 0                      # it exited while we were walking
    close = line.rfind(")")
    if close < 0:
        return 0
    fields = line[close + 1:].split()
    if len(fields) < 2:
        return 0
    return int(fields[1])             # fields[0] is the state letter


def alive(pid):
    return os.path.exists("/proc/%d" % pid)


def read_roots_file(path):
    # A missing file is not an error. It only means nothing has registered
    # itself yet, which is the normal state before the first agent starts.
    found = set()
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    found.add(int(line))
    except OSError:
        pass
    return found


def sweep(path):
    # Pids only ever flow IN from the file. The agent runs as our user, so
    # it could delete its own line to escape supervision; we therefore treat
    # the file as an inbox, never as the current truth. A root is dropped
    # only when its process is gone, which the agent cannot fake.
    global last_sweep

    now = time.time()
    if now - last_sweep < SWEEP_SECONDS:
        return
    last_sweep = now

    for pid in read_roots_file(path):
        if pid not in roots:
            roots.add(pid)
            # Anything we previously decided was unsupervised may now sit
            # under this new root, so the old answers cannot be trusted.
            supervised_cache.clear()

    for pid in list(roots):
        if not alive(pid):
            roots.discard(pid)

    # Drop cached answers for pids that are gone, so a pid the kernel hands
    # out again does not inherit the answer we gave the previous owner.
    for pid in list(supervised_cache):
        if not alive(pid):
            del supervised_cache[pid]


def supervising_root(pid):
    # Returns the root that supervises this pid, or None if it is not part
    # of the agent. Cached because this runs on every single open and a walk
    # costs one small file read per step.
    if pid in supervised_cache:
        return supervised_cache[pid]

    answer = None
    walk = pid
    depth = 0
    while walk > 1 and depth < MAX_DEPTH:
        if walk in roots:
            answer = walk
            break
        walk = parent_of(walk)
        depth = depth + 1

    supervised_cache[pid] = answer
    return answer


def decide(policies, path):
    action, note = db.check(policies, path)

    # Keep the history up to date whatever the rules say, so the score
    # sees everything the agent touched.
    risk.record(path)

    # A hard rule wins outright. We do not want a well-behaved agent to
    # earn its way into credentials by looking calm first.
    if action == "block":
        return FAN_DENY, note

    points, why = risk.score()

    if risk.is_risky(points):
        return FAN_DENY, "risk %d: %s" % (points, why)

    if action == "allow":
        return FAN_ALLOW, note

    return FAN_ALLOW, "no rule"

def answer(fan_fd, event_fd, verdict):
    os.write(fan_fd, struct.pack("<iI", event_fd, verdict))


def main():
    if len(sys.argv) < 2:
        print("usage: sudo python3 daemon.py <folder> [--roots <file>]")
        sys.exit(1)

    folder = sys.argv[1]
    roots_path = DEFAULT_ROOTS
    if len(sys.argv) == 4 and sys.argv[2] == "--roots":
        roots_path = sys.argv[3]
    elif len(sys.argv) != 2:
        print("usage: sudo python3 daemon.py <folder> [--roots <file>]")
        sys.exit(1)

    if not os.path.isdir(folder):
        print("not a folder:", folder)
        sys.exit(1)

    fan_fd = start_fanotify()

    # FAN_EVENT_ON_CHILD only reaches files directly inside a marked folder,
    # not subfolders. So we walk the tree and mark every folder we find.
    marked = 0
    for folder_path, dirs, files in os.walk(folder):
        watch_folder(fan_fd, folder_path)
        marked = marked + 1
    print("marked %d folders" % marked)

    policies = db.load_policies()
    writer.start()

    print("watching %s" % folder)
    print("loaded %d policy rules" % len(policies))
    print("agent roots file: %s" % roots_path)
    print()

    my_pid = os.getpid()

    while True:
        data = os.read(fan_fd, 4096)
        offset = 0
        while offset < len(data):
            fields = struct.unpack_from(EVENT_FORMAT, data, offset)
            event_len, version, reserved, meta_len, mask, event_fd, pid = fields
            offset = offset + event_len

            if event_fd < 0:
                continue

            if pid == my_pid:
                answer(fan_fd, event_fd, FAN_ALLOW)
                os.close(event_fd)
                continue

            sweep(roots_path)

            path = path_of(event_fd)
            root = supervising_root(pid)

            if root is None:
                # Not part of the agent tree. We stay out of its way, but we
                # still log it so we can show what we chose not to touch.
                verdict, reason = FAN_ALLOW, "not supervised"
            else:
                verdict, reason = decide(policies, path)

            name = name_of_process(pid)

            print("%-8s pid=%-7d %s  ->  %s (%s)" % (
                name, pid, path,
                "ALLOW" if verdict == FAN_ALLOW else "DENY", reason))

            # Answer the kernel FIRST so the paused process gets going again.
            answer(fan_fd, event_fd, verdict)
            os.close(event_fd)

            # Then record it. Nobody is waiting on this.
            writer.record(pid, name, path,
                          "allow" if verdict == FAN_ALLOW else "block",
                          reason)


# Guarded so the supervision helpers above can be imported and tested
# without starting the daemon, which needs root.
if __name__ == "__main__":
    main()
