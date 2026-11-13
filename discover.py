"""Find companies' own job boards from the Simplify list and add them to config.json.

Simplify links each internship to the company's application page. When that page is on
Greenhouse, Lever or Ashby, we can watch the company's board directly, which catches new
postings as soon as the company publishes them instead of waiting for Simplify's list.

Only companies with active US SWE, data/AI, quant or hardware internships are added. Workday boards are skipped
(each needs dozens of requests per check); Simplify still covers those companies.

Run:  .venv/bin/python discover.py
"""
from concurrent.futures import ThreadPoolExecutor

from check import load_config, save_config
from fetchers import FETCHERS, make_client, parse_board_url
from location import is_us
from sections import SIMPLIFY_CATEGORIES

DIRECT_PLATFORMS = {"greenhouse", "lever", "ashby"}


def _responds(entry, client):
    try:
        FETCHERS[entry["platform"]](entry, client)
        return True
    except Exception:
        return False


def main():
    cfg = load_config()
    simplify = next(c for c in cfg["companies"] if c["platform"] == "simplify")
    with make_client() as client:
        listings = client.get(simplify["url"]).json()

    tracked = {(c["platform"], c.get("slug") or c.get("tenant")) for c in cfg["companies"]}
    tracked_names = {c["name"].lower() for c in cfg["companies"]}
    added = []
    for x in listings:
        if not (x.get("active") and x.get("is_visible", True)):
            continue
        if x.get("category") not in SIMPLIFY_CATEGORIES:  # SWE, data/AI, quant, hardware
            continue
        if not any(is_us(loc) for loc in x.get("locations") or []):
            continue
        entry = parse_board_url(x["url"], x["company_name"])
        if not entry or entry["platform"] not in DIRECT_PLATFORMS:
            continue
        key = (entry["platform"], entry["slug"])
        if key in tracked or entry["name"].lower() in tracked_names:
            continue
        tracked.add(key)
        tracked_names.add(entry["name"].lower())
        added.append(entry)

    # Keep only boards that actually respond; some links use names the public API doesn't know.
    with make_client() as client, ThreadPoolExecutor(max_workers=16) as pool:
        ok = list(pool.map(lambda e: _responds(e, client), added))
    added = [e for e, good in zip(added, ok) if good]
    cfg["companies"].extend(added)
    save_config(cfg)
    by_platform = {p: sum(1 for e in added if e["platform"] == p) for p in DIRECT_PLATFORMS}
    print(f"Added {len(added)} company boards {by_platform}. Now tracking {len(cfg['companies'])} sources.")


if __name__ == "__main__":
    main()
