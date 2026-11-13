"""The MCP server. This is what lets Claude use the job tracker as a set of tools.

Each function decorated with @mcp.tool() becomes a tool Claude can call. Claude sees the
function name, the docstring (as the description) and the type hints (as the input schema),
and decides on its own when calling one would help answer your question.
"""
from typing import Literal

from mcp.server.mcpserver import MCPServer

import db
from check import load_config, run_check, save_config
from fetchers import FETCHERS, make_client, parse_board_url

mcp = MCPServer("job-tracker")


@mcp.tool()
def check_for_new_jobs() -> dict:
    """Check every tracked company right now and return internship postings that are new since the last check."""
    new, errors, total = run_check()
    for j in new:
        j.pop("description", None)
        j.pop("detail_api", None)
    return {"new_jobs": new, "matching_postings_tracked": total, "errors": errors}


@mcp.tool()
def list_jobs(query: str = "",
              sponsorship: Literal["Sponsors", "Does not sponsor", "Not specified"] | None = None,
              us_only: bool = True,
              posted_within_hours: int | None = None) -> list[dict]:
    """List saved internship postings (newest posted first) with company, role, location, posted date/time
    and visa sponsorship status. Filters: words in title/company/location, sponsorship, US-only (default on),
    and posted_within_hours (e.g. 24 for jobs posted in the last day)."""
    conn = db.connect()
    try:
        return db.search(conn, query, sponsorship, us_only, posted_within_hours)
    finally:
        conn.close()


@mcp.tool()
def recent_jobs(hours: int = 24) -> list[dict]:
    """List internship postings this tracker first noticed within the last N hours."""
    conn = db.connect()
    try:
        return db.recent(conn, hours)
    finally:
        conn.close()


@mcp.tool()
def list_companies() -> list[dict]:
    """List the companies being tracked and which hiring platform each uses."""
    return load_config()["companies"]


@mcp.tool()
def add_company(name: str, careers_url: str) -> str:
    """Start tracking a company, given its careers-page URL on Greenhouse, Lever, Ashby or Workday.

    Examples: https://jobs.lever.co/palantir, https://jobs.ashbyhq.com/ramp,
    https://boards.greenhouse.io/stripe, https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
    """
    entry = parse_board_url(careers_url, name)
    if not entry:
        return "Couldn't recognize that URL as a Greenhouse, Lever, Ashby or Workday job board."
    cfg = load_config()
    if any(c["name"].lower() == name.lower() for c in cfg["companies"]):
        return f"{name} is already being tracked."
    try:
        with make_client() as client:
            count = len(FETCHERS[entry["platform"]](entry, client))
    except Exception as e:
        return f"That board didn't respond correctly ({e}); not added."
    cfg["companies"].append(entry)
    save_config(cfg)
    return f"Now tracking {name} on {entry['platform']} ({count} open postings found). Run check_for_new_jobs to load them."


if __name__ == "__main__":
    mcp.run()  # talks to Claude over stdin/stdout
