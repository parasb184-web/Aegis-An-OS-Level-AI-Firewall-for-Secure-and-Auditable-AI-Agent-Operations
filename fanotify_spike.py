import ctypes
import os
import struct
import sys

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


def decide(path):
    if "secret" in os.path.basename(path):
        return FAN_DENY
    return FAN_ALLOW


def answer(fan_fd, event_fd, verdict):
    os.write(fan_fd, struct.pack("<iI", event_fd, verdict))


def main():
    if len(sys.argv) != 2:
        print("usage: sudo python3 fanotify_spike.py <folder>")
        sys.exit(1)

    folder = sys.argv[1]
    if not os.path.isdir(folder):
        print("not a folder:", folder)
        sys.exit(1)

    fan_fd = start_fanotify()
    watch_folder(fan_fd, folder)
    print("watching %s" % folder)
    print("(files with 'secret' in the name will be denied)")
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
            verdict = decide(path)

            print("%-8s pid=%-7d %s  ->  %s" % (
                name_of_process(pid), pid, path,
                "ALLOW" if verdict == FAN_ALLOW else "DENY"))

            answer(fan_fd, event_fd, verdict)
            os.close(event_fd)



main()
