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


def decide(policies, path):
    action, note = db.check(policies, path)

    # Keep the history up to date whatever the rules say, so the score
    # sees everything the agent touched.
    risk.record(path)

    # A hard rule wins outright. We do not want a well-behaved agent to
    # earn its way into credentials by looking calm first.
    if action == "block":
        return FAN_DENY, note

    points, why = risk.score(path, action == "block")

    if risk.is_risky(points):
        return FAN_DENY, "risk %d: %s" % (points, why)

    if action == "allow":
        return FAN_ALLOW, note

    return FAN_ALLOW, "no rule"

def answer(fan_fd, event_fd, verdict):
    os.write(fan_fd, struct.pack("<iI", event_fd, verdict))


def main():
    if len(sys.argv) != 2:
        print("usage: sudo python3 daemon.py <folder>")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print("not a folder:", folder)
        sys.exit(1)

    fan_fd = start_fanotify()
       # FAN_EVENT_ON_CHILD only reaches files directly inside a marked folder,
    # not subfolders. So we walk the tree and mark every folder we find.
    marked = 0
    for root, dirs, files in os.walk(folder):
        watch_folder(fan_fd, root)
        marked = marked + 1
    print("marked %d folders" % marked)

    policies = db.load_policies()
    writer.start()

    print("watching %s" % folder)
    print("loaded %d policy rules" % len(policies))
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

            path = path_of(event_fd)
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


main()