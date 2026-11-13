"""Build jobs.html: one page listing tracked postings with posted date/time, US filter and sponsorship.

Run by hand to rebuild and open it:  .venv/bin/python report.py
"""
import json
import subprocess
from pathlib import Path

REPORT_PATH = Path(__file__).parent / "jobs.html"

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Internship Tracker</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1d1d1f;--muted:#6b6b70;--line:#e4e4e0;--accent:#2f5bd3;
  --yes:#1f7a3d;--yes-bg:#e3f4e8;--no:#b42318;--no-bg:#fde8e6;--na:#5f5f66;--na-bg:#eeeeec;--new:#8a4b00;--new-bg:#fff1d6}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--card:#1c1c1f;--ink:#ececef;--muted:#9a9aa2;--line:#2c2c31;
  --accent:#7c9cff;--yes:#6fd393;--yes-bg:#173222;--no:#ff8a80;--no-bg:#3a1a18;--na:#b0b0b8;--na-bg:#2a2a2e;--new:#ffc56b;--new-bg:#3a2a10}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1200px;margin:0 auto;padding:28px 16px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 18px}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:10px}
.label{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);min-width:86px}
input{flex:1;min-width:200px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit}
.chip{padding:6px 12px;border:1px solid var(--line);border-radius:999px;background:var(--card);color:var(--ink);cursor:pointer;font:inherit}
.chip[aria-pressed=true]{border-color:var(--accent);color:var(--accent);font-weight:600}
.wrap{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow-x:auto;margin-top:14px}
table{width:100%;border-collapse:collapse;min-width:760px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap}
th[data-dir=asc]::after{content:" \\2191"}th[data-dir=desc]::after{content:" \\2193"}
tr:last-child td{border-bottom:0}
a{color:var(--accent);text-decoration:none;font-weight:600}a:hover{text-decoration:underline}
.co{font-weight:600;white-space:nowrap}.src{font-weight:400;color:var(--muted);font-size:11px}.loc{color:var(--muted);max-width:260px}
.when{white-space:nowrap}.when small{color:var(--muted)}.when b{font-weight:600}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600;white-space:nowrap}
.Sponsors{color:var(--yes);background:var(--yes-bg)}.Does{color:var(--no);background:var(--no-bg)}.Not{color:var(--na);background:var(--na-bg)}
.new{color:var(--new);background:var(--new-bg);margin-left:6px}
details{margin-top:4px;color:var(--muted);font-size:12px;max-width:340px}summary{cursor:pointer}
.empty{padding:40px;text-align:center;color:var(--muted)}
</style></head><body><main>
<h1>Internship Tracker</h1>
<p class="sub" id="sub"></p>
<div class="bar"><input id="q" type="search" placeholder="Search role, company, location…"></div>
<div class="bar"><span class="label">Posted</span>
  <button class="chip" data-g="win" data-v="24">Last 24 hours</button>
  <button class="chip" data-g="win" data-v="72">3 days</button>
  <button class="chip" data-g="win" data-v="168">7 days</button>
  <button class="chip" data-g="win" data-v="">All time</button></div>
<div class="bar"><span class="label">Section</span>
  <button class="chip" data-g="sec" data-v="">All</button>
  <button class="chip" data-g="sec" data-v="swe">SWE</button>
  <button class="chip" data-g="sec" data-v="quant">Quant</button>
  <button class="chip" data-g="sec" data-v="finance">Finance</button>
  <button class="chip" data-g="sec" data-v="hardware">Hardware</button>
  <button class="chip" data-g="sec" data-v="events">Events &amp; programs</button></div>
<div class="bar"><span class="label">Location</span>
  <button class="chip" data-g="us" data-v="1">US only</button>
  <button class="chip" data-g="us" data-v="">All countries</button></div>
<div class="bar"><span class="label">Sponsorship</span>
  <button class="chip" data-g="sp" data-v="">Any</button>
  <button class="chip" data-g="sp" data-v="Sponsors">Sponsors</button>
  <button class="chip" data-g="sp" data-v="Does not sponsor">Does not sponsor</button>
  <button class="chip" data-g="sp" data-v="Not specified">Not specified</button></div>
<div class="wrap"><table>
<thead><tr><th data-k="company">Company</th><th data-k="title">Role</th><th data-k="location">Location</th>
<th data-k="posted" data-dir="desc">Posted</th><th data-k="sponsorship">Sponsorship</th></tr></thead>
<tbody id="rows"></tbody></table><div class="empty" id="empty" hidden></div></div>
</main>
<script>
const JOBS = __DATA__;
const GENERATED = "__GENERATED__";
const state = {win: "24", us: "1", sp: "", sec: ""};
const SECTION = {swe: "SWE", quant: "Quant", finance: "Finance", hardware: "Hardware", events: "Event / program", other: "Other"};
let sortKey = "posted", sortDir = -1;
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const dateOnly = iso => iso && iso.length === 10;  // Workday gives a date with no time
const parse = iso => new Date(dateOnly(iso) ? iso + "T00:00:00" : iso);
// Date-only postings are measured from the end of that day, so "today" and "yesterday" count as < 24h.
const ageHours = iso => !iso ? Infinity : Math.max(0, (Date.now() - parse(iso) - (dateOnly(iso) ? 864e5 : 0)) / 36e5);
function ago(iso){
  if(!iso) return "";
  if(dateOnly(iso)){
    const today = new Date(); today.setHours(0,0,0,0);
    const days = Math.round((today - parse(iso)) / 864e5);
    return days <= 0 ? "today" : days === 1 ? "yesterday" : days + " days ago";
  }
  const h = (Date.now() - parse(iso)) / 36e5;
  return h < 1 ? Math.max(1, Math.round(h * 60)) + " min ago" : h < 24 ? Math.floor(h) + " hr ago"
       : h < 48 ? "yesterday" : Math.floor(h / 24) + " days ago";
}
function when(iso){
  if(!iso) return "Unknown";
  const d = parse(iso);
  const date = d.toLocaleDateString(undefined, {weekday:"short", month:"short", day:"numeric", year:"numeric"});
  const time = dateOnly(iso) ? "time not listed" : d.toLocaleTimeString(undefined, {hour:"numeric", minute:"2-digit"});
  return `<b>${date}</b><br><small>${time} · ${ago(iso)}</small>`;
}
const isNew = j => j.first_seen && Date.now() - new Date(j.first_seen) < 864e5 && j.first_seen > BASELINE;
const BASELINE = JOBS.reduce((m, j) => j.first_seen && j.first_seen < m ? j.first_seen : m, "9999");
function render(){
  const q = document.getElementById("q").value.toLowerCase();
  const list = JOBS.filter(j =>
      (!state.us || j.us) &&
      (state.sec ? j.section === state.sec : j.section !== "other") &&
      (!state.win || ageHours(j.posted) <= +state.win) &&
      (!state.sp || j.sponsorship === state.sp) &&
      (j.title + " " + j.company + " " + j.location).toLowerCase().includes(q))
    .sort((a, b) => sortKey === "posted"
      ? (Math.min(ageHours(a.posted), 1e9) - Math.min(ageHours(b.posted), 1e9)) * -sortDir  // smaller age = newer
      : String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? "")) * sortDir);
  document.getElementById("rows").innerHTML = list.map(j => `<tr>
    <td class="co">${esc(j.company)}<br><small class="src">${esc(SECTION[j.section] || "")} · ${j.platform === "simplify" ? "via Simplify" : "company site"}</small></td>
    <td><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>${isNew(j) ? '<span class="badge new">NEW</span>' : ""}</td>
    <td class="loc">${esc(j.location)}</td>
    <td class="when">${when(j.posted)}</td>
    <td><span class="badge ${esc((j.sponsorship || "Not").split(" ")[0])}">${esc(j.sponsorship || "Not specified")}</span>
      ${j.sponsorship_evidence ? `<details><summary>Why?</summary>“${esc(j.sponsorship_evidence)}”</details>` : ""}</td></tr>`).join("");
  const empty = document.getElementById("empty");
  empty.hidden = list.length > 0;
  empty.textContent = state.win ? "Nothing posted in this window yet. Try 3 days or 7 days." : "No postings match.";
  const c = s => list.filter(j => j.sponsorship === s).length;
  document.getElementById("sub").textContent = `Showing ${list.length} of ${JOBS.length} postings · ${c("Sponsors")} sponsor · ${c("Does not sponsor")} don't · ${c("Not specified")} not specified · updated ${new Date(GENERATED).toLocaleString()}`;
}
function sync(){ document.querySelectorAll(".chip").forEach(b => b.setAttribute("aria-pressed", state[b.dataset.g] === b.dataset.v)); }
document.getElementById("q").addEventListener("input", render);
document.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => { state[b.dataset.g] = b.dataset.v; sync(); render(); }));
document.querySelectorAll("th").forEach(th => th.addEventListener("click", () => {
  sortDir = sortKey === th.dataset.k ? -sortDir : (th.dataset.k === "posted" ? -1 : 1);
  sortKey = th.dataset.k;
  document.querySelectorAll("th").forEach(x => x.removeAttribute("data-dir"));
  th.dataset.dir = sortDir > 0 ? "asc" : "desc"; render();
}));
sync(); render();
</script></body></html>
"""


def write(jobs):
    from db import now
    rows = [{k: j.get(k) for k in ("company", "platform", "title", "location", "url", "us", "posted",
                                   "first_seen", "sponsorship", "sponsorship_evidence", "section")}
            for j in jobs]
    data = json.dumps(rows).replace("</", "<\\/")  # keep job text from closing the <script> tag
    REPORT_PATH.write_text(PAGE.replace("__DATA__", data).replace("__GENERATED__", now()))


if __name__ == "__main__":
    import db
    conn = db.connect()
    write(db.all_jobs(conn))
    conn.close()
    subprocess.run(["open", str(REPORT_PATH)])
