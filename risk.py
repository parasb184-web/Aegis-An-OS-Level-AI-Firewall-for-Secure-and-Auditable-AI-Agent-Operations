import os
import time
from typing import Dict, List, Optional, Tuple

# Public API surface of this module
__all__ = ["record", "trim", "forget", "score", "is_warning", "is_risky"]

# Sliding window in seconds over which file-open events are counted
WINDOW: float = 10.0

FILE_LIMIT: int = 15      
FOLDER_LIMIT: int = 4     
WARN_AT: int = 30        
BLOCK_AT: int = 40       

history: Dict[int, List[Tuple[float, str]]] = {}


def record(root: int, path: str) -> None:
    """Record a file open event for an agent process tree."""
    now = time.time()
    history.setdefault(root, []).append((now, os.path.dirname(path)))
    trim(now)


def trim(now: float) -> None:
    """Evict records older than the sliding window."""
    cutoff = now - WINDOW
    for root in list(history):
        opens = history[root]
        while opens and opens[0][0] < cutoff:
            opens.pop(0)
        if not opens:
            del history[root]


def forget(root: int) -> None:
    """Clear all history for a terminated agent process tree."""
    history.pop(root, None)


def score(root: int) -> Tuple[int, str]:
    """Calculate the cumulative risk score and justification for an agent."""
    opens = history.get(root, [])
    files = len(opens)
    folders = len(set(folder for when, folder in opens))

    points = 0
    reasons: List[str] = []

    if files > FILE_LIMIT:
        points = points + 40
        reasons.append("%d files in %ds" % (files, int(WINDOW)))

    if folders > FOLDER_LIMIT:
        points = points + 30
        reasons.append("%d folders" % folders)

    return points, ", ".join(reasons)


def is_warning(points: int) -> bool:
    """Check if the score warrants a warning without blocking."""
    return WARN_AT <= points < BLOCK_AT


def is_risky(points: int) -> bool:
    """Check if the score exceeds the blocking threshold."""
    return points >= BLOCK_AT


if __name__ == "__main__":
    for i in range(30):
        p = "/home/test/notes/file%d.txt" % i
        record(1234, p)
        pts, why = score(1234)
        if i % 10 == 0 or is_risky(pts):
            print("file %-3d score %-4d %s" % (i, pts, why))
            if is_risky(pts):
                break
