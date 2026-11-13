"""Fetch job postings from each hiring platform and convert them to one common shape.

Every job, no matter which platform it came from, becomes a dict like:
    {"id", "company", "platform", "title", "location", "url", "posted", "description"}
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx

from sections import is_event

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
    # The list without descriptions is ~10x smaller; descriptions are fetched only for new jobs.
    api = f"https://boards-api.greenhouse.io/v1/boards/{c['slug']}/jobs"
    r = client.get(api)
    r.raise_for_status()
    return [
        _job("greenhouse", c["slug"], j["id"], c["name"], j["title"],
             (j.get("location") or {}).get("name"), j["absolute_url"],
             j.get("first_published") or j.get("updated_at"), None, detail_api=f"{api}/{j['id']}")
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
    jobs = {}
    for search in c.get("searches", ["intern"]):  # banks say "summer analyst" rather than "intern"
        offset, total = 0, None
        while offset < WORKDAY_MAX_JOBS:
            r = client.post(f"{api}/jobs", json={"appliedFacets": {}, "limit": WORKDAY_PAGE_SIZE,
                                                 "offset": offset, "searchText": search})
            r.raise_for_status()
            data = r.json()
            if total is None:
                total = data.get("total", 0)
            page = data.get("jobPostings", [])
            for j in page:
                if not j.get("externalPath") or not j.get("title"):
                    continue  # Workday occasionally returns incomplete entries; one shouldn't sink the whole company
                jobs[j["externalPath"]] = _job(
                    "workday", c["tenant"], j["externalPath"], c["name"], j["title"],
                    j.get("locationsText"), f"{base}/{c['site']}{j['externalPath']}",
                    _workday_relative_date(j.get("postedOn")), None, detail_api=f"{api}{j['externalPath']}")
            offset += WORKDAY_PAGE_SIZE
            if not page or offset >= total:
                break
    return list(jobs.values())


ORACLE_PAGE_SIZE = 25
ORACLE_MAX_JOBS = 250


def fetch_oracle(c, client):
    """Oracle Cloud careers sites (JPMorgan, American Express). Results come newest first."""
    api = f"https://{c['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    jobs = {}
    for search in c.get("searches", ["intern"]):
        for offset in range(0, ORACLE_MAX_JOBS, ORACLE_PAGE_SIZE):
            finder = (f'findReqs;siteNumber={c["site"]},keyword="{search}",limit={ORACLE_PAGE_SIZE},'
                      f"offset={offset},sortBy=POSTING_DATES_DESC")
            r = client.get(api, params={"onlyData": "true", "finder": finder,
                                        "expand": "requisitionList.secondaryLocations"})
            r.raise_for_status()
            page = (r.json().get("items") or [{}])[0].get("requisitionList") or []
            for j in page:
                locations = [j.get("PrimaryLocation")] + [s.get("Name") for s in j.get("secondaryLocations") or []]
                jobs[j["Id"]] = _job(
                    "oracle", c["host"].split(".")[0], j["Id"], c["name"], j["Title"],
                    " • ".join(l for l in locations if l),
                    f"https://{c['host']}/hcmUI/CandidateExperience/en/sites/{c['site']}/job/{j['Id']}",
                    j.get("PostedDate"), "", country=j.get("PrimaryLocationCountry"))
            if len(page) < ORACLE_PAGE_SIZE:
                break
    return list(jobs.values())


EIGHTFOLD_MAX_PAGES = 10  # 10 results per page


def fetch_eightfold(c, client):
    """Eightfold careers sites (Morgan Stanley). Sorted newest first."""
    base = f"https://{c['host']}"
    jobs = {}
    for search in c.get("searches", ["intern"]):
        for page_num in range(EIGHTFOLD_MAX_PAGES):
            r = client.get(f"{base}/api/pcsx/search", params={
                "domain": c["domain"], "query": search, "start": page_num * 10, "sort_by": "timestamp"})
            r.raise_for_status()
            page = r.json()["data"]["positions"]
            for j in page:
                jobs[j["id"]] = _job(
                    "eightfold", c["domain"], j["id"], c["name"], j["name"],
                    " • ".join(j.get("standardizedLocations") or j.get("locations") or []),
                    f"{base}{j['positionUrl']}",
                    datetime.fromtimestamp(j["postedTs"], tz=timezone.utc).isoformat(), "")
            if len(page) < 10:
                break
    return list(jobs.values())


SIMPLIFY_SPONSORSHIP = {
    "Offers Sponsorship": "Sponsors",
    "Does Not Offer Sponsorship": "Does not sponsor",
    "U.S. Citizenship is Required": "Does not sponsor",
}


def fetch_simplify(c, client):
    """The SimplifyJobs internship list on GitHub: ~1,000+ companies, maintained by Simplify and students.

    Every listing is already an internship, and Simplify labels sponsorship and role category.
    """
    r = client.get(c["url"])
    r.raise_for_status()
    jobs = []
    for x in r.json():
        if not x.get("active") or not x.get("is_visible", True):
            continue
        job = _job("simplify", "simplify", x["id"], x["company_name"], x["title"],
                   " • ".join(x.get("locations") or []), x["url"],
                   datetime.fromtimestamp(x["date_posted"], tz=timezone.utc).isoformat(), "")
        job["category"] = x.get("category") or ""
        job["sponsorship_label"] = SIMPLIFY_SPONSORSHIP.get(x.get("sponsorship"), "Not specified")
        job["sponsorship_note"] = f"Simplify: {x.get('sponsorship')}" if x.get("sponsorship") else ""
        jobs.append(job)
    return jobs


def fill_details(job, client):
    """Fetch a job's own page for the description (Greenhouse, Workday) and full locations (Workday)."""
    r = client.get(job["detail_api"])
    r.raise_for_status()
    if job["platform"] == "greenhouse":
        job["description"] = html_to_text(r.json().get("content"))
        return job
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
    "oracle": fetch_oracle,
    "eightfold": fetch_eightfold,
    "simplify": fetch_simplify,
}


def make_client():
    return httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True)  # some big boards are slow


def fetch_all(companies, client):
    """Fetch every company in parallel. Returns (jobs, errors) where errors maps company -> message."""
    jobs, errors = [], {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {c["name"]: pool.submit(FETCHERS[c["platform"]], c, client) for c in companies}
        for name, f in futures.items():
            try:
                for j in f.result():
                    j["source"] = name  # which config entry it came from (Simplify lists many companies)
                    jobs.append(j)
            except Exception as e:
                errors[name] = f"{type(e).__name__}: {e}"
    return jobs, errors


def _hit(patterns, text):
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def matches(job, filters):
    """True if this is an internship or student program/event we track.
    Simplify listings are all internships already."""
    if _hit(filters.get("exclude", []), job["title"]):
        return False
    return (job["platform"] == "simplify" or is_event(job["title"])
            or _hit(filters.get("include", [".*"]), job["title"]))


def parse_board_url(url, name):
    """Turn a careers-page URL into a company config entry, e.g.
    https://jobs.lever.co/palantir -> {"name": ..., "platform": "lever", "slug": "palantir"}
    """
    patterns = [
        ("greenhouse", r"greenhouse\.io/embed/job_app\?(?:.*&)?for=([\w-]+)"),
        ("greenhouse", r"(?:job-)?boards(?:-api)?\.greenhouse\.io/(?:v1/boards/)?(?!embed/)([\w-]+)"),
        ("lever", r"jobs\.lever\.co/([\w-]+)"),
        ("ashby", r"jobs\.ashbyhq\.com/([\w.-]+)"),
    ]
    for platform, pat in patterns:
        m = re.search(pat, url)
        if m:
            return {"name": name, "platform": platform, "slug": m.group(1)}
    m = re.search(r"([\w.-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[\w-]+/sites/(\w+)", url)
    if m:
        return {"name": name, "platform": "oracle", "host": m.group(1), "site": m.group(2)}
    m = re.search(r"([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)", url)
    if m:
        return {"name": name, "platform": "workday", "tenant": m.group(1), "wd": m.group(2), "site": m.group(3)}
    return None
