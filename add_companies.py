"""Add the companies in targets.txt that aren't tracked yet.

For each new company:
  1. If Simplify lists it, use the job board its postings link to (most reliable; covers
     Greenhouse, Lever, Ashby, Workday and Oracle).
  2. Otherwise guess board names on Greenhouse, Lever and Ashby from the company name.
     Greenhouse guesses are kept only if the board's own company name matches.
  3. Keep the board only if it responds.

Companies on custom career sites (Apple, Google, Goldman Sachs…) can't be checked directly;
the report says whether Simplify still covers them.

Run:  .venv/bin/python add_companies.py
"""
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from check import load_config, save_config
from fetchers import FETCHERS, make_client, parse_board_url

TARGETS_PATH = Path(__file__).parent / "targets.txt"
SUFFIXES = r"\b(inc|llc|corp|corporation|company|co|group|holdings|technologies|technology|systems|global|markets|labs|solutions)\b"


def words(name):
    return re.sub(r"[^a-z0-9 ]", " ", name.lower().replace("&", " and ")).split()


def same_company(alias, other):
    """True if `other` starts with all the words of `alias` (so "Lockheed Martin" matches
    "Lockheed Martin Corporation" but "ICE" doesn't match "Service Now")."""
    a, o = words(alias), words(other)
    return bool(a) and o[:len(a)] == a


def load_targets():
    targets = []
    for line in TARGETS_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            aliases = [a.strip() for a in line.split("|") if a.strip()]
            targets.append(aliases)
    return targets


def slug_guesses(name):
    base = re.sub(SUFFIXES, "", name.lower()).strip()
    full = re.sub(r"[^a-z0-9]", "", name.lower())
    short = re.sub(r"[^a-z0-9]", "", base)
    dashed = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return list(dict.fromkeys(s for s in (full, short, dashed) if len(s) >= 3))


def guess_board(aliases, client):
    for alias in aliases:
        for slug in slug_guesses(alias):
            r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")
            if r.status_code == 200:
                jobs = r.json().get("jobs", [])
                owner = jobs[0].get("company_name", "") if jobs else ""
                if owner and any(same_company(a, owner) or same_company(owner, a) for a in aliases):
                    return {"name": aliases[0], "platform": "greenhouse", "slug": slug}
            for platform, url in (("lever", f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1"),
                                  ("ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}")):
                # No company name to verify against, so only accept specific (longer) names.
                if len(slug) >= 6 and client.get(url).status_code == 200:
                    return {"name": aliases[0], "platform": platform, "slug": slug}
    return None


def board_from_simplify(aliases, listings):
    boards = Counter()
    entries = {}
    for x in listings:
        if any(same_company(a, x["company_name"]) for a in aliases):
            e = parse_board_url(x["url"], aliases[0])
            if e:
                key = tuple(sorted((k, v) for k, v in e.items() if k != "name"))
                boards[key] += 1
                entries[key] = e
    return entries[boards.most_common(1)[0][0]] if boards else None


def on_simplify(aliases, listings):
    return any(same_company(a, x["company_name"]) for a in aliases for x in listings if x.get("active"))


def responds(entry, client):
    try:
        FETCHERS[entry["platform"]](entry, client)
        return True
    except Exception:
        return False


def main():
    cfg = load_config()
    tracked = [c["name"] for c in cfg["companies"]]
    simplify = next(c for c in cfg["companies"] if c["platform"] == "simplify")

    with make_client() as client:
        listings = client.get(simplify["url"]).json()
        new_targets = [t for t in load_targets()
                       if not any(same_company(a, n) or same_company(n, a) for a in t for n in tracked)]
        already = len(load_targets()) - len(new_targets)

        def find(aliases):
            urls = [a for a in aliases if a.startswith("http")]
            aliases = [a for a in aliases if not a.startswith("http")]
            entry = ((urls and parse_board_url(urls[0], aliases[0]))
                     or board_from_simplify(aliases, listings) or guess_board(aliases, client))
            return aliases, (entry if entry and responds(entry, client) else None)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(find, new_targets))

    # Boards checked and found to be a different company (e.g. "Apple" -> Apple Bank) are listed
    # in config.json's ignored_boards so they're never re-added.
    ignored = set(cfg.get("ignored_boards", []))
    added, simplify_only, missing = [], [], []
    for aliases, entry in results:
        aliases = [a for a in aliases if not a.startswith("http")]
        if entry and f'{entry["platform"]}:{entry.get("slug") or entry.get("tenant")}' in ignored:
            entry = None
        if entry:
            if entry["platform"] == "workday":
                entry["searches"] = ["intern", "co-op"]
            cfg["companies"].append(entry)
            added.append(entry)
        elif on_simplify(aliases, listings):
            simplify_only.append(aliases[0])
        else:
            missing.append(aliases[0])
    save_config(cfg)

    print(f"Already tracked: {already}")
    print(f"\nAdded {len(added)} company boards (checked directly every run):")
    for e in added:
        print(f"  + {e['name']:<28} {e['platform']}")
    print(f"\nCovered through Simplify only ({len(simplify_only)}; custom career sites):")
    print("  " + ", ".join(simplify_only))
    print(f"\nNot found ({len(missing)}; no public job board or not on Simplify):")
    print("  " + ", ".join(missing))


if __name__ == "__main__":
    main()
