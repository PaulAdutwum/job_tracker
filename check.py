"""Check every company once, save results, rebuild the jobs page, and notify about new postings.

Run by hand:      .venv/bin/python check.py
Or on a schedule: see README.md
"""
import fcntl
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

import db
import report
from fetchers import fetch_all, fill_details, make_client, matches
from location import is_us
from sections import LABELS, section_of
from sponsorship import classify

CONFIG_PATH = Path(__file__).parent / "config.json"
# A job we haven't seen before isn't necessarily new: it may have just moved into the search
# results. Only alert on jobs the company actually posted recently.
ALERT_MAX_AGE_HOURS = 72


def load_config():
    return json.loads(CONFIG_PATH.read_text())


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2) + "\n")


def run_check():
    """Returns (new_jobs, errors, matching_count)."""
    cfg = load_config()
    conn = db.connect()
    try:
        with make_client() as client:
            jobs, errors = fetch_all(cfg["companies"], client)
            jobs = [j for j in jobs if matches(j, cfg["filters"])]

            # Only do the extra work (detail pages, sponsorship scan) for jobs we haven't stored.
            known = db.known_ids(conn, [j["id"] for j in jobs])
            unseen = [j for j in jobs if j["id"] not in known]
            db.backfill_sections(conn, section_of)

            # The same posting can come from a company's own board and from one or more community
            # lists (Simplify, vanshb03); keep the direct one, else the first list that has it.
            direct = {(j["company"].lower(), j["title"].lower()) for j in jobs if j["platform"] != "simplify"}
            seen_titles = db.known_titles(conn) | direct
            kept = []
            for j in unseen:
                key = (j["company"].lower(), j["title"].lower())
                if j["platform"] != "simplify":
                    kept.append(j)
                elif key not in seen_titles:
                    seen_titles.add(key)
                    kept.append(j)
            unseen = kept

            needs_detail = [j for j in unseen if j["description"] is None]
            failed = {}
            with ThreadPoolExecutor(max_workers=8) as pool:
                for job, f in [(j, pool.submit(fill_details, j, client)) for j in needs_detail]:
                    try:
                        f.result()
                    except Exception:
                        job["description"] = ""  # keep the job; sponsorship will show "Not specified"
                        failed[job["company"]] = failed.get(job["company"], 0) + 1
            for company, n in failed.items():
                errors[f"{company} (details)"] = f"{n} job pages couldn't be loaded; sponsorship unknown for those"

        seen_at = db.now()
        for j in unseen:
            if j["platform"] == "simplify":
                j["sponsorship"], j["sponsorship_evidence"] = j["sponsorship_label"], j["sponsorship_note"]
            else:
                j["sponsorship"], j["sponsorship_evidence"] = classify(j["description"])
            j["us"] = int(is_us(j["location"], j["country"]))
            j["section"] = section_of(j)
            j["first_seen"] = seen_at

        fetched = [c["name"] for c in cfg["companies"] if c["name"] not in errors]
        new = db.save_new_jobs(conn, unseen, fetched)
        if cfg["filters"].get("us_only", True):
            new = [j for j in new if j["us"]]  # non-US jobs are still saved, just not alerted on
        alert_sections = cfg["filters"].get("alert_sections", list(LABELS))
        new = [j for j in new if j["section"] in alert_sections]  # same for sections you don't follow
        new = [j for j in new
               if (h := db.hours_since_posted(j["posted"])) is not None and h <= ALERT_MAX_AGE_HOURS]
        report.write(db.all_jobs(conn))
    finally:
        conn.close()
    return new, errors, len(jobs)


def notify(new_jobs):
    if not new_jobs:
        return
    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        notify_phone(new_jobs, topic)
    elif sys.platform == "darwin":
        notify_mac(new_jobs)


def notify_phone(new_jobs, topic):
    """Push to the ntfy app (https://ntfy.sh). Tapping the notification opens the posting."""
    for j in new_jobs[:10]:
        try:
            httpx.post("https://ntfy.sh/", timeout=15, json={
                "topic": topic,
                "title": f"New {LABELS.get(j['section'], 'internship')}: {j['company']}",
                "message": f"{j['title']}\n{j['location']} · {j['sponsorship']}",
                "click": j["url"],
                "tags": ["briefcase"],
            }).raise_for_status()
        except httpx.HTTPError as e:
            print(f"  ntfy failed: {e}")


def notify_mac(new_jobs):
    first = new_jobs[0]
    title = f"{len(new_jobs)} new internship posting(s)"
    body = f"{first['company']}: {first['title']} ({first['sponsorship']})"
    if len(new_jobs) > 1:
        body += f" +{len(new_jobs) - 1} more"
    # json.dumps produces a double-quoted, escaped string that AppleScript accepts
    script = f"display notification {json.dumps(body)} with title {json.dumps(title)} sound name \"Glass\""
    subprocess.run(["osascript", "-e", script], check=False)


def main():
    # Only one check at a time, so a manual run and the scheduled run can't race each other.
    lock = open(Path(__file__).parent / ".check.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Another check is already running; skipping.")
        return
    new, errors, total = run_check()
    print(f"[{db.now()}] {total} matching postings tracked, {len(new)} new US.  Page: {report.REPORT_PATH}")
    for j in new:
        print(f"  NEW  {j['company']:<12} {j['title']}  [{j['location']}]  {j['sponsorship']}\n       {j['url']}")
    for name, err in errors.items():
        print(f"  ERROR {name}: {err}")
    notify(new)


if __name__ == "__main__":
    main()
