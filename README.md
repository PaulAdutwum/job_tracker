# Internship Tracker (MCP server)

Watches ~350 sources for internships and student programs, sorts them into **SWE, Quant,
Finance, Hardware and Events & programs**, flags visa sponsorship, alerts your phone, and lets
Claude query it all as tools.

**Sources**
- **Company job boards, checked directly:** Greenhouse, Lever, Ashby, Workday (Citi, Barclays,
  BlackRock, Capital One, NVIDIA, Salesforce), Oracle (JPMorgan, American Express)
- **SimplifyJobs Summer 2027 list:** ~1,350 companies, including firms whose sites we can't read
  directly (Goldman Sachs, Citadel, Jane Street, Meta, Amazon…)
- `discover.py` finds more company boards from Simplify's links; re-run it now and then
- `targets.txt` is your own company list; `add_companies.py` adds any that aren't tracked yet
  and reports which are covered only by Simplify or not found

**Sections** are assigned in `sections.py` from the title (and Simplify's category).
Alerts fire for the sections in `alert_sections` in `config.json`.

## How it works

```
config.json ──► fetchers.py ──► filter titles ──► sponsorship.py ──► db.py (SQLite)
 companies +     one function     "intern",         reads each new      remembers every
 title filters   per platform     "co-op"…          description         job ever seen
                                                                              │
                     check.py (run on a schedule) ◄──────────────────────────┤
                       → macOS notification for NEW jobs                      │
                       → rebuilds jobs.html (report.py)                       │
                                                                              │
                     server.py (MCP) ◄────────────────────────────────────────┘
                       → Claude can call: check_for_new_jobs, list_jobs,
                         recent_jobs, list_companies, add_company
```

| File | What it teaches |
|---|---|
| `fetchers.py` | Calling public JSON APIs; normalizing 4 different data shapes into 1; pagination (Workday) |
| `sponsorship.py` | Text classification with regex; keeping evidence so results are checkable |
| `db.py` | SQLite; "what's new?" by diffing against what's stored |
| `check.py` | Orchestration; parallel requests with a thread pool; OS notifications |
| `server.py` | **MCP**: each `@mcp.tool()` function becomes a tool Claude can call. The docstring is the tool's description and the type hints are its input schema. |

**Why ATS APIs are fast:** a company's own board updates the moment a recruiter hits publish.
LinkedIn/Handshake/aggregators pick it up hours or days later.

**First run** records everything already open as a baseline (no alerts). After that, only
genuinely new postings trigger a notification.

**Sponsorship labels** are keyword-based: `Sponsors`, `Does not sponsor`, `Not specified`.
A required security clearance counts as "Does not sponsor" (clearances need citizenship).
Click **Why?** on the page to see the sentence that decided it. Always confirm on the posting.

## Use it

```bash
cd ~/Documents/myprojects/job-tracker
.venv/bin/python check.py     # check now, print new jobs, update jobs.html
.venv/bin/python report.py    # open the jobs page
```

In Claude Code (any folder), just ask:
- "Any new internships today?"
- "List software internships that sponsor visas"
- "Start tracking https://jobs.ashbyhq.com/linear as Linear"

## Add companies

Find the company's careers page. The URL tells you the platform:

| URL looks like | Platform |
|---|---|
| `boards.greenhouse.io/<slug>` or `job-boards.greenhouse.io/<slug>` | Greenhouse |
| `jobs.lever.co/<slug>` | Lever |
| `jobs.ashbyhq.com/<slug>` | Ashby |
| `<tenant>.wd5.myworkdayjobs.com/<site>` | Workday |

Ask Claude to add it (uses the `add_company` tool), or edit `config.json` by hand.
Change `filters` in `config.json` to track other roles (they're regular expressions).

## Deployed on GitHub Actions (runs 24/7)

`.github/workflows/check.yml` runs `check.py` every 30 minutes in the cloud:

1. Restores `jobs.db` from the Actions cache (so it remembers what it has seen)
2. Fetches all companies, detects new US postings
3. Sends a phone notification through [ntfy](https://ntfy.sh) for each new posting (tap to open it)
4. Saves `jobs.db` back to the cache
5. Publishes the jobs page to GitHub Pages

Setup: add a repo secret `NTFY_TOPIC` (your private ntfy channel name), set
**Settings → Pages → Source** to **GitHub Actions**, and subscribe to the same topic in the ntfy app.
Use **Actions → Check for new internships → Run workflow** to trigger a check by hand.

Notes: the first cloud run records a baseline (no alerts). GitHub pauses scheduled workflows in
repos with no commits for 60 days; push any commit to re-enable. Public repos get unlimited
Actions minutes; a private repo would exceed the free tier at this frequency.

## Runs locally every 30 min (optional)

A macOS `launchd` agent (`~/Library/LaunchAgents/com.jobtracker.check.plist`) runs `check.py`
every 30 minutes while you're logged in, and catches up after the Mac wakes from sleep.
Output goes to `check.log`.

```bash
tail -20 check.log                                                        # see recent checks
launchctl kickstart gui/$(id -u)/com.jobtracker.check                     # run a check now
launchctl bootout gui/$(id -u)/com.jobtracker.check                       # stop the schedule
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobtracker.check.plist  # start it again
```

To change the interval, edit `StartInterval` (seconds) in the plist, then stop and start it.

Alerts fire only for US jobs the company posted in the last 72 hours (`ALERT_MAX_AGE_HOURS`
in `check.py`). Workday sorts search results by relevance, not date, so a job can appear in
results days after it was posted; the age check keeps those from showing up as "new".

## Ideas to extend it (good portfolio upgrades)
- Location filter (US only, NYC, remote)
- Use Claude to classify sponsorship instead of regex, and compare accuracy
- Push alerts to your phone (ntfy.sh, Discord/Slack webhook)
- Auto-add new postings to a Notion tracker
- Add SmartRecruiters / iCIMS fetchers
- Tests (`pytest`) for `sponsorship.classify` and `parse_board_url`
