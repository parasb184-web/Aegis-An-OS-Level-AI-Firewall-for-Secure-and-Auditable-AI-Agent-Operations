"""Aegis Database Layer: PostgreSQL connection management and policy engine.

Loads firewall rules from the 'policies' table and provides wildcard pattern
matching against filesystem paths.
"""

import fnmatch
import os
from typing import List, Optional, Tuple
import psycopg2
from psycopg2.extensions import connection as PgConnection


# Database connection string, configurable via AEGIS_DB environment variable
DB: str = os.environ.get(
    "AEGIS_DB",
    "dbname=aegis user=aegis password=aegis host=localhost"
)


def connect() -> PgConnection:
    """Establish and return a new PostgreSQL connection."""
    return psycopg2.connect(DB)


def load_policies() -> List[Tuple[str, str, str, Optional[str]]]:
    """Load active firewall policies ordered so that block actions take precedence.
    
    Translates SQL '%' wildcards into fnmatch '*' pattern wildcards.
    """
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT path_pattern, sensitivity, action, note FROM policies "
        "ORDER BY CASE action WHEN 'block' THEN 0 ELSE 1 END, id"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    policies: List[Tuple[str, str, str, Optional[str]]] = []
    for pattern, sensitivity, action, note in rows:
        policies.append((pattern.replace("%", "*"), sensitivity, action, note))
    return policies


def check(
    policies: List[Tuple[str, str, str, Optional[str]]],
    path: str
) -> Tuple[Optional[str], Optional[str]]:
    """Match a filesystem path against loaded policies in priority order.
    
    Returns:
        (action, note) if a pattern matches, otherwise (None, None).
    """
    for pattern, sensitivity, action, note in policies:
        if fnmatch.fnmatch(path, pattern):
            return action, note
    return None, None


if __name__ == "__main__":
    p = load_policies()
    print("loaded %d rules" % len(p))
    for test in ["/home/acerparas/.ssh/id_rsa",
                 "/home/acerparas/project/main.py",
                 "/home/acerparas/notes.txt"]:
        print(test, "->", check(p, test))
