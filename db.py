"""SQLite storage: remembers every job we've seen so we can tell which ones are new."""
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    company TEXT, platform TEXT, title TEXT, location TEXT, url TEXT,
    us INTEGER,                  -- 1 if any location is in the United States
    posted TEXT,                 -- when the company published it (Workday gives a date only)
    first_seen TEXT,             -- when this tracker first noticed it
    sponsorship TEXT,            -- Sponsors / Does not sponsor / Not specified
    sponsorship_evidence TEXT,   -- the sentence that decided it
    category TEXT,               -- Simplify's role category, when available
    section TEXT,                -- swe / quant / finance / hardware / events / other (see sections.py)
    baseline INTEGER,            -- 1 if recorded on its source's first check (already open, not new)
    source TEXT                  -- config entry it came from: a company, "Simplify" or "vanshb03"
);
CREATE TABLE IF NOT EXISTS companies_seen (name TEXT PRIMARY KEY);
"""

COLUMNS = ["id", "company", "platform", "title", "location", "url", "us", "posted",
           "first_seen", "sponsorship", "sponsorship_evidence", "category", "section", "baseline", "source"]
# Columns added after the first version; older databases get them on connect.
ADDED_COLUMNS = {"category": "TEXT", "section": "TEXT", "baseline": "INTEGER", "source": "TEXT"}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)")}
    for name, kind in ADDED_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {kind}")
    if "source" not in existing:  # older rows: tell the two community lists apart by their links
        conn.execute("UPDATE jobs SET source = CASE WHEN url LIKE '%vansh%' THEN 'vanshb03' ELSE 'Simplify' END "
                     "WHERE platform = 'simplify'")
        conn.execute("UPDATE jobs SET source = company WHERE platform != 'simplify'")
        conn.commit()
    return conn


def known_titles(conn):
    """(company, title) pairs already stored, lowercased, for spotting duplicates across sources."""
    return {(r["company"].lower(), r["title"].lower()) for r in conn.execute("SELECT company, title FROM jobs")}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def hours_since_posted(posted):
    """Hours since a job was posted, or None if unknown.

    Date-only values (Workday) are measured from the end of that day, so anything
    posted today or yesterday counts as "within 24 hours".
    """
    if not posted:
        return None
    try:
        d = datetime.fromisoformat(posted.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        return max(0.0, (datetime.now() - (d + timedelta(days=1))).total_seconds() / 3600)
    return (datetime.now(timezone.utc) - d).total_seconds() / 3600


def known_ids(conn, ids):
    ids = list(ids)
    found = set()
    for i in range(0, len(ids), 500):  # SQLite limits how many ? placeholders one query can have
        chunk = ids[i:i + 500]
        rows = conn.execute(f"SELECT id FROM jobs WHERE id IN ({','.join('?' * len(chunk))})", chunk)
        found.update(r["id"] for r in rows)
    return found


def backfill_sections(conn, section_of):
    """Fill section for jobs stored before that column existed."""
    rows = conn.execute("SELECT id, title, category FROM jobs WHERE section IS NULL").fetchall()
    conn.executemany("UPDATE jobs SET section = ? WHERE id = ?", [(section_of(dict(r)), r["id"]) for r in rows])


def save_new_jobs(conn, jobs, fetched_sources):
    """Insert jobs that aren't stored yet and return the ones worth alerting about.

    The first time a source (a company board, or Simplify) is checked, its existing jobs are
    recorded silently as a baseline, so you aren't flooded with hundreds of "new" alerts on day one.
    """
    baselined = {r["name"] for r in conn.execute("SELECT name FROM companies_seen")}
    for j in jobs:
        j["baseline"] = int(j["source"] not in baselined)
        if not j.get("posted") and not j["baseline"]:
            j["posted"] = j["first_seen"]  # platforms without a posting date: when we first saw it
    placeholders = ", ".join(f":{c}" for c in COLUMNS)
    conn.executemany(f"INSERT OR IGNORE INTO jobs ({', '.join(COLUMNS)}) VALUES ({placeholders})",
                     [{c: j.get(c) for c in COLUMNS} for j in jobs])
    conn.executemany("INSERT OR IGNORE INTO companies_seen (name) VALUES (?)",
                     [(s,) for s in fetched_sources])
    conn.commit()
    return [j for j in jobs if j["source"] in baselined]


def _newest_first(rows):
    def age(r):
        h = hours_since_posted(r["posted"])
        return float("inf") if h is None else h
    return sorted(rows, key=age)


def all_jobs(conn):
    return _newest_first([dict(r) for r in conn.execute("SELECT * FROM jobs")])


def recent(conn, hours):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    rows = conn.execute("SELECT * FROM jobs WHERE first_seen >= ? ORDER BY first_seen DESC", (since,))
    return [dict(r) for r in rows]


def search(conn, query="", sponsorship=None, us_only=True, posted_within_hours=None,
           section=None, limit=100):
    like = f"%{query}%"
    sql = "SELECT * FROM jobs WHERE (title LIKE ? OR company LIKE ? OR location LIKE ?)"
    params = [like, like, like]
    if sponsorship:
        sql += " AND sponsorship = ?"
        params.append(sponsorship)
    if us_only:
        sql += " AND us = 1"
    if section:
        sql += " AND section = ?"
        params.append(section)
    rows = [dict(r) for r in conn.execute(sql, params)]
    if posted_within_hours is not None:
        rows = [r for r in rows
                if (h := hours_since_posted(r["posted"])) is not None and h <= posted_within_hours]
    return _newest_first(rows)[:limit]
