"""Aegis Kernel Firewall Monitoring Daemon.

Uses Linux fanotify in permission mode (FAN_OPEN_PERM) to intercept file open
events across monitored directories. Evaluates process trees against PostgreSQL
security policies and the dynamic sliding-window risk engine before responding to
the Linux kernel with FAN_ALLOW or FAN_DENY.
"""

import ctypes
import json
import os
import signal
import struct
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import db
from typing import Any, Dict, List, Optional, Set, Tuple

import db
import risk
import writer

# Load Linux C library for fanotify syscalls (with fallback for static analysis on Windows)
try:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
except (OSError, AttributeError):
    libc = None

# Linux fanotify bit flags
FAN_CLOEXEC: int        = 0x00000001  # Close-on-exec flag on new file descriptor
FAN_CLASS_CONTENT: int  = 0x00000004  # Permission events before access; content inspection
FAN_OPEN_PERM: int      = 0x00010000  # File open permission event (blocks until answered)
FAN_EVENT_ON_CHILD: int = 0x08000000  # Include child directory events
FAN_MARK_ADD: int       = 0x00000001  # Add directory to fanotify watch list
FAN_CLOEXEC: int        = 0x00000001  
FAN_CLASS_CONTENT: int  = 0x00000004  
FAN_OPEN_PERM: int      = 0x00010000  
FAN_EVENT_ON_CHILD: int = 0x08000000  
FAN_MARK_ADD: int       = 0x00000001  

# Kernel response verdicts
FAN_ALLOW: int          = 0x01        # Grant permission to open file
FAN_DENY: int           = 0x02        # Deny open with EPERM
FAN_ALLOW: int          = 0x01        
FAN_DENY: int           = 0x02       

AT_FDCWD: int           = -100        # Special fd for current working directory
O_RDONLY: int           = 0
AT_FDCWD: int           = -100       
O_RDONLY: int           = 0

DEFAULT_ROOTS: str      = "/tmp/aegis_roots"
SWEEP_SECONDS: float    = 1.0
MAX_DEPTH: int          = 40
DEFAULT_STATUS: str     = "/tmp/aegis_status.json"
DEFAULT_ROOTS: str      = "/tmp/aegis_roots"
SWEEP_SECONDS: float    = 1.0
MAX_DEPTH: int          = 40
DEFAULT_STATUS: str     = "/tmp/aegis_status.json"

# Binary struct format for struct fanotify_event_metadata:
# < (little endian) I (event_len) B (vers) B (reserved) H (metadata_len) Q (mask) i (fd) i (pid)
EVENT_FORMAT: str       = "<IBBHQii"

EVENT_FORMAT: str       = "<IBBHQii"

if libc is not None:
    libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
    libc.fanotify_mark.argtypes = [
        ctypes.c_int,
        ctypes.c_uint,
        ctypes.c_uint64,
        ctypes.c_int,
        ctypes.c_char_p,
    ]


def start_fanotify() -> int:
    """Initialize fanotify in permission mode (requires CAP_SYS_ADMIN)."""
    if libc is None:
        print("fanotify requires Linux glibc (libc.so.6).")
        sys.exit(1)
libc.fanotify_mark.argtypes = [
    ctypes.c_int,
    ctypes.c_uint,
    ctypes.c_uint64,
    ctypes.c_int,
    ctypes.c_char_p,
]

def start_fanotify() -> int:
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

def watch_folder(fan_fd: int, folder: str) -> None:
    """Mark a directory path for child permission event interception."""
    if libc is None:
        return
    result = libc.fanotify_mark(
        fan_fd,
        FAN_MARK_ADD,
        FAN_OPEN_PERM | FAN_EVENT_ON_CHILD,
        AT_FDCWD,
        folder.encode(),
    )
def watch_folder(fan_fd: int, folder: str) -> None:
    result = libc.fanotify_mark(
        fan_fd,
        FAN_MARK_ADD,
        FAN_OPEN_PERM | FAN_EVENT_ON_CHILD,
        AT_FDCWD,
        folder.encode(),
    )
    if result < 0:
        print("fanotify_mark failed:", os.strerror(ctypes.get_errno()))
        sys.exit(1)

def path_of(fd: int) -> str:
    """Resolve file path associated with the event file descriptor."""
def path_of(fd: int) -> str:
    try:
        return os.readlink("/proc/self/fd/%d" % fd)
    except OSError:
        return "<unknown>"

def name_of_process(pid: int) -> str:
    """Read the executable name of a process from /proc/<pid>/comm."""
def name_of_process(pid: int) -> str:
    try:
        with open("/proc/%d/comm" % pid) as f:
            return f.read().strip()
    except OSError:
        return "<gone>"

status_path: Optional[str] = None
watching: Optional[str] = None
roots_file: Optional[str] = None
status_path: Optional[str] = None
watching: Optional[str] = None
roots_file: Optional[str] = None

roots: Set[int] = set()
supervised_cache: Dict[int, Optional[int]] = {}
roots_mtime: float = -1.0
last_sweep: float = 0.0
roots: Set[int] = set()
supervised_cache: Dict[int, Optional[int]] = {}
roots_mtime: float = -1.0
last_sweep: float = 0.0

def parent_of(pid: int) -> int:
    """Extract parent PID (PPID) by reading /proc/<pid>/stat."""
def parent_of(pid: int) -> int:
    try:
        with open("/proc/%d/stat" % pid) as f:
            line = f.read()
    except OSError:
        return 0
    close = line.rfind(")")
    if close < 0:
        return 0
    fields = line[close + 1:].split()
    if len(fields) < 2:
        return 0
    return int(fields[1])

def alive(pid: int) -> bool:
    """Check if process directory still exists in /proc."""
def alive(pid: int) -> bool:
    return os.path.exists("/proc/%d" % pid)

def read_roots_file(path: str) -> Set[int]:
    """Parse agent root PIDs from the shared roots registry file."""
    found: Set[int] = set()
def read_roots_file(path: str) -> Set[int]:
    found: Set[int] = set()
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    found.add(int(line))
    except OSError:
        pass
    return found

def refresh_roots(path: str) -> None:
    """Check file modification time and reload agent roots when updated."""
def refresh_roots(path: str) -> None:
    global roots_mtime

    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return
    if mtime == roots_mtime:
        return
    roots_mtime = mtime

    for pid in read_roots_file(path):
        if pid not in roots:
            roots.add(pid)
            supervised_cache.clear()

def sweep(path: str) -> None:
    """Prune terminated root PIDs and refresh heartbeat status."""
def sweep(path: str) -> None:
    global roots_mtime, last_sweep

    now = time.time()
    if now - last_sweep < SWEEP_SECONDS:
        return
    last_sweep = now

    for pid in list(roots):
        if not alive(pid):
            roots.discard(pid)
            risk.forget(pid)

    for pid in list(supervised_cache):
        if not alive(pid):
            del supervised_cache[pid]

    roots_mtime = -1.0
    publish_status()

def publish_status() -> None:
    """Write daemon heartbeat and active agent status atomically to status JSON."""
def publish_status() -> None:
    if not status_path:
        return

    agents = []
    now = time.time()
    for root in sorted(roots):
        opens = risk.history.get(root, [])
        points, why = risk.score(root)
        agents.append({
            "root": root,
            "name": name_of_process(root),
            "files": len(opens),
            "folders": len(set(folder for when, folder in opens)),
            "score": points,
            "why": why,
        })

    state = {
        "pid": os.getpid(),
        "at": now,
        "watching": watching,
        "roots_file": roots_file,
        "window": risk.WINDOW,
        "file_limit": risk.FILE_LIMIT,
        "folder_limit": risk.FOLDER_LIMIT,
        "warn_at": risk.WARN_AT,
        "block_at": risk.BLOCK_AT,
        "agents": agents,
    }

    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(status_path) or ".")
        with os.fdopen(fd, "w") as f:
            json.dump(state, f)
        os.chmod(tmp, 0o644)
        os.replace(tmp, status_path)
    except OSError:
        pass

def supervising_root(pid: int) -> Optional[int]:
    """Walk up parent chain to discover if process descends from an agent root."""
def supervising_root(pid: int) -> Optional[int]:
    if pid in supervised_cache:
        return supervised_cache[pid]

    result = None
    result = None
    walk = pid
    depth = 0
    while walk > 1 and depth < MAX_DEPTH:
        if walk in roots:
            result = walk
            result = walk
            break
        walk = parent_of(walk)
        depth = depth + 1

    supervised_cache[pid] = result
    return result
    supervised_cache[pid] = result
    return result

def decide(
    policies: List[Tuple[str, str, str, Optional[str]]],
    path: str,
    root: int
) -> Tuple[int, str, str]:
    """Evaluate target path against database policies and risk score."""
def decide(
    policies: List[Tuple[str, str, str, Optional[str]]],
    path: str,
    root: int
) -> Tuple[int, str, str]:
    action, note = db.check(policies, path)

    risk.record(root, path)

    if action == "block":
        return FAN_DENY, "block", note or "blocked by policy"
        return FAN_DENY, "block", note or "blocked by policy"

    points, why = risk.score(root)

    if risk.is_risky(points):
        return FAN_DENY, "block", "risk %d: %s" % (points, why)

    if risk.is_warning(points):
        return FAN_ALLOW, "warn", "risk %d: %s" % (points, why)

    if action == "allow":
        return FAN_ALLOW, "allow", note or "allowed by policy"
        return FAN_ALLOW, "allow", note or "allowed by policy"

    return FAN_ALLOW, "allow", "no rule"


def on_signal(signum: int, frame: Any) -> None:
    """Handle termination signals cleanly."""

def on_signal(signum: int, frame: Any) -> None:
    raise KeyboardInterrupt

def answer(fan_fd: int, event_fd: int, verdict: int) -> None:
    """Respond to Linux fanotify kernel with permission verdict struct."""
def answer(fan_fd: int, event_fd: int, verdict: int) -> None:
    os.write(fan_fd, struct.pack("<iI", event_fd, verdict))

def main() -> None:
    """Main fanotify event loop."""
def main() -> None:
    if len(sys.argv) < 2:
        print("usage: sudo python3 daemon.py <folder> [--roots <file>]")
        sys.exit(1)

    folder = sys.argv[1]
    roots_path = DEFAULT_ROOTS
    status = DEFAULT_STATUS

    rest = sys.argv[2:]
    while rest:
        if rest[0] == "--roots" and len(rest) > 1:
            roots_path = rest[1]
            rest = rest[2:]
            roots_path = rest[1]
            rest = rest[2:]
        elif rest[0] == "--status" and len(rest) > 1:
            status = rest[1]
            rest = rest[2:]
            status = rest[1]
            rest = rest[2:]
        else:
            print("usage: sudo python3 daemon.py <folder> "
                  "[--roots <file>] [--status <file>]")
            sys.exit(1)

    if not os.path.isdir(folder):
        print("not a folder:", folder)
        sys.exit(1)

    fan_fd = start_fanotify()

    marked = 0
    for folder_path, dirs, files in os.walk(folder):
        watch_folder(fan_fd, folder_path)
        marked = marked + 1
    print("marked %d folders" % marked)

    policies = db.load_policies()
    writer.start()

    global status_path, watching, roots_file
    status_path = status
    watching = folder
    roots_file = roots_path
    publish_status()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    print("watching %s" % folder)
    print("loaded %d policy rules" % len(policies))
    print("agent roots file: %s" % roots_path)
    print("status file: %s" % status)
    print()

    my_pid = os.getpid()

    try:
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

                refresh_roots(roots_path)
                sweep(roots_path)

                path = path_of(event_fd)
                root = supervising_root(pid)

                if root is None:
                    verdict, label, reason = FAN_ALLOW, "allow", "not supervised"
                else:
                    verdict, label, reason = decide(policies, path, root)

                name = name_of_process(pid)

                print("%-8s pid=%-7d %s  ->  %s (%s)" % (
                    name, pid, path, label.upper(), reason))

                answer(fan_fd, event_fd, verdict)
                os.close(event_fd)

                writer.record(pid, name, path, label, reason)

    except KeyboardInterrupt:
        pass

    try:
        os.remove(status_path)
    except OSError:
        pass

    print()
    print("stopping, flushing the audit log ...")
    if writer.stop():
        print("stopped")
    else:
        print("writer did not finish, exiting anyway")
        os._exit(1)

if __name__ == "__main__":
    main()


