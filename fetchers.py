"""Fetch job postings from each hiring platform and convert them to one common shape.

Every job, no matter which platform it came from, becomes a dict like:
    {"id", "company", "platform", "title", "location", "url", "posted", "description"}
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx

HEADERS = {"User-Agent": "personal-job-tracker"}
WORKDAY_PAGE_SIZE = 20  # Workday rejects anything larger
WORKDAY_MAX_JOBS = 2000  # results are sorted by relevance, not date, so read them all


def html_to_text(s):
    """Strip HTML tags so we can search the plain words."""
    s = html.unescape(s or "")  # Greenhouse double-encodes its HTML
    s = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(s)).strip()


def _job(platform, key, job_id, company, title, location, url, posted, description,
         country=None, detail_api=None):
    return {
        "id": f"{platform}:{key}:{job_id}",  # unique across all platforms
        "company": company,
        "platform": platform,
        "title": (title or "").strip(),
        "location": location or "",
        "country": country,  # only some platforms provide it
        "url": url,
        "posted": posted or "",
        "description": description,  # None means "needs a second request" (Workday)
        "detail_api": detail_api,
    }


# --- One fetcher per platform ------------------------------------------------

def fetch_greenhouse(c, client):
    r = client.get(f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs", params={"content": "true"})
    r.raise_for_status()
    return [
        _job("greenhouse", c["slug"], j["id"], c["name"], j["title"],
             (j.get("location") or {}).get("name"), j["absolute_url"],
             j.get("first_published") or j.get("updated_at"), html_to_text(j.get("content")))
        for j in r.json()["jobs"]
    ]


def fetch_lever(c, client):
    r = client.get(f"https://api.lever.co/v0/postings/{c['slug']}", params={"mode": "json"})
    r.raise_for_status()
    jobs = []
    for j in r.json():
        parts = [j.get("descriptionPlain", ""), j.get("additionalPlain", "")]
        parts += [html_to_text(l.get("content")) for l in j.get("lists", [])]
        cats = j.get("categories") or {}
        jobs.append(_job("lever", c["slug"], j["id"], c["name"], j["text"],
                         " • ".join(cats.get("allLocations") or []) or cats.get("location"), j["hostedUrl"],
                         datetime.fromtimestamp(j["createdAt"] / 1000, tz=timezone.utc).isoformat(),
                         "\n".join(parts), country=j.get("country")))
    return jobs


def fetch_ashby(c, client):
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{c['slug']}")
    r.raise_for_status()
    jobs = []
    for j in r.json()["jobs"]:
        if not j.get("isListed", True):
            continue
        locations = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations", [])]
        country = (((j.get("address") or {}).get("postalAddress")) or {}).get("addressCountry")
        jobs.append(_job("ashby", c["slug"], j["id"], c["name"], j["title"],
                         " • ".join(l for l in locations if l), j["jobUrl"], j.get("publishedAt"),
                         j.get("descriptionPlain", ""), country=country))
    return jobs


def _workday_relative_date(posted_on):
    """Turn Workday's 'Posted 3 Days Ago' into an approximate date (fallback only)."""
    text = (posted_on or "").lower()
    if "today" in text:
        return date.today().isoformat()
    if "yesterday" in text:
        return (date.today() - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s+days", text)
    return (date.today() - timedelta(days=int(m.group(1)))).isoformat() if m else ""


def fetch_workday(c, client):
    # Workday has no official public API. Its career sites call this JSON endpoint,
    # which pages 20 at a time and only reports "total" on the first page.
    base = f"https://{c['tenant']}.{c['wd']}.myworkdayjobs.com"
    api = f"{base}/wday/cxs/{c['tenant']}/{c['site']}"
    jobs, offset, total = [], 0, None
    while offset < WORKDAY_MAX_JOBS:
        r = client.post(f"{api}/jobs", json={"appliedFacets": {}, "limit": WORKDAY_PAGE_SIZE,
                                             "offset": offset, "searchText": c.get("search", "intern")})
        r.raise_for_status()
        data = r.json()
        if total is None:
            total = data.get("total", 0)
        page = data.get("jobPostings", [])
        for j in page:
            if not j.get("externalPath") or not j.get("title"):
                continue  # Workday occasionally returns incomplete entries; one shouldn't sink the whole company
            jobs.append(_job("workday", c["tenant"], j["externalPath"], c["name"], j["title"],
                             j.get("locationsText"), f"{base}/{c['site']}{j['externalPath']}",
                             _workday_relative_date(j.get("postedOn")), None,
                             detail_api=f"{api}{j['externalPath']}"))
        offset += WORKDAY_PAGE_SIZE
        if not page or offset >= total:
            break
    return jobs


def fill_workday_details(job, client):
    """Workday's list doesn't include descriptions or full locations; fetch the job's own page."""
    r = client.get(job["detail_api"])
    r.raise_for_status()
    info = r.json()["jobPostingInfo"]
    job["description"] = html_to_text(info.get("jobDescription"))
    job["posted"] = info.get("startDate") or job["posted"]
    locations = [info.get("location")] + (info.get("additionalLocations") or [])
    job["location"] = " • ".join(l for l in locations if l) or job["location"]  # replaces "2 Locations"
    job["country"] = (info.get("country") or {}).get("descriptor")
    return job


FETCHERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
}


def make_client():
    return httpx.Client(headers=HEADERS, timeout=30, follow_redirects=True)


def fetch_all(companies, client):
    """Fetch every company in parallel. Returns (jobs, errors) where errors maps company -> message."""
    jobs, errors = [], {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {c["name"]: pool.submit(FETCHERS[c["platform"]], c, client) for c in companies}
        for name, f in futures.items():
            try:
                jobs.extend(f.result())
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"
    return jobs, errors


def matches(title, filters):
    """True if the title matches any include pattern and no exclude pattern."""
    hit = lambda pats: any(re.search(p, title, re.IGNORECASE) for p in pats)
    return hit(filters.get("include", [".*"])) and not hit(filters.get("exclude", []))


def parse_board_url(url, name):
    """Turn a careers-page URL into a company config entry, e.g.
    https://jobs.lever.co/palantir -> {"name": ..., "platform": "lever", "slug": "palantir"}
    """
    patterns = [
        ("greenhouse", r"(?:job-)?boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?([\w-]+)"),
        ("lever", r"jobs\.lever\.co/([\w-]+)"),
        ("ashby", r"jobs\.ashbyhq\.com/([\w.-]+)"),
    ]
    for platform, pat in patterns:
        m = re.search(pat, url)
        if m:
            return {"name": name, "platform": platform, "slug": m.group(1)}
    m = re.search(r"([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)", url)
    if m:
        return {"name": name, "platform": "workday", "tenant": m.group(1), "wd": m.group(2), "site": m.group(3)}
    return None
