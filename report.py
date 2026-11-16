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
input[type=search]{flex:1;min-width:200px;padding:9px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit}
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
nav.tabs{position:sticky;top:0;z-index:5;background:var(--bg);display:flex;gap:4px;overflow-x:auto;
  scrollbar-width:none;border-bottom:1px solid var(--line);margin:0 -16px 14px;padding:8px 16px}
nav.tabs::-webkit-scrollbar{display:none}
.tab{padding:8px 12px;border-radius:8px;color:var(--muted);font-weight:600;white-space:nowrap}
.tab:hover{text-decoration:none;color:var(--ink)}
.tab[aria-current=page]{background:var(--card);color:var(--accent);box-shadow:0 0 0 1px var(--line)}
.tab .n{font-weight:400;font-size:12px;margin-left:4px;opacity:.8}
.pager{display:flex;gap:6px;justify-content:center;align-items:center;flex-wrap:wrap;margin:16px 0}
.pager button{min-width:40px;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit;cursor:pointer}
.pager button[aria-current=page]{border-color:var(--accent);color:var(--accent);font-weight:700}
.pager button:disabled{opacity:.4;cursor:default}.pager span{color:var(--muted);padding:0 4px}
.ap{width:18px;height:18px;margin:2px 0 0;cursor:pointer;accent-color:var(--accent)}td.apcell{text-align:center}
@media (max-width:720px){
  main{padding:0 16px 24px;max-width:100vw;overflow-x:hidden}h1{font-size:19px;margin-top:14px}
  .bar{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding-bottom:2px}.bar::-webkit-scrollbar{display:none}
  .label{min-width:auto;flex:none}.chip{flex:none}input[type=search]{min-width:0;font-size:16px}
  .wrap{border:0;background:none;overflow:visible}
  table,tbody{display:block;min-width:0;width:100%}thead{display:none}
  tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:2px 12px;background:var(--card);border:1px solid var(--line);
     border-radius:12px;padding:12px 14px;margin-bottom:10px}
  td{display:block;border:0;padding:0;min-width:0;overflow-wrap:anywhere}
  td.role{grid-column:1/-1;order:-1;font-size:15px}
  td.co{white-space:normal}td.loc{grid-column:1/-1;max-width:none}
  td.when{grid-column:1/2;white-space:normal}td.when br{display:none}td.when small::before{content:" · "}
  td.spon{grid-column:1/2}td.apcell{grid-column:2;grid-row:2/4;align-self:center;text-align:center}
  td.apcell::after{content:"Applied";display:block;font-size:11px;color:var(--muted)}
  .ap{width:24px;height:24px}details{max-width:none}
}
</style></head><body><main>
<nav class="tabs" id="tabs"></nav>
<h1>Internship Tracker</h1>
<p class="sub" id="sub"></p>
<div class="bar"><input id="q" type="search" placeholder="Search role, company, location…"></div>
<div class="bar"><span class="label">Posted</span>
  <button class="chip" data-g="win" data-v="new">New since last visit</button>
  <button class="chip" data-g="win" data-v="24">Last 24 hours</button>
  <button class="chip" data-g="win" data-v="72">3 days</button>
  <button class="chip" data-g="win" data-v="168">7 days</button>
  <button class="chip" data-g="win" data-v="">All time</button></div>
<div class="bar"><span class="label">Location</span>
  <button class="chip" data-g="us" data-v="1">US only</button>
  <button class="chip" data-g="us" data-v="">All countries</button></div>
<div class="bar"><span class="label">Sponsorship</span>
  <button class="chip" data-g="sp" data-v="">Any</button>
  <button class="chip" data-g="sp" data-v="Sponsors">Sponsors</button>
  <button class="chip" data-g="sp" data-v="Does not sponsor">Does not sponsor</button>
  <button class="chip" data-g="sp" data-v="Not specified">Not specified</button></div>
<div class="bar"><span class="label">Status</span>
  <button class="chip" data-g="st" data-v="todo">Not applied</button>
  <button class="chip" data-g="st" data-v="done">Applied</button>
  <button class="chip" data-g="st" data-v="">All</button></div>
<div class="wrap"><table>
<thead><tr><th data-k="company">Company</th><th data-k="title">Role</th><th data-k="location">Location</th>
<th data-k="posted" data-dir="desc">Posted</th><th data-k="sponsorship">Sponsorship</th><th>Applied</th></tr></thead>
<tbody id="rows"></tbody></table><div class="empty" id="empty" hidden></div></div>
<div class="pager" id="pager"></div>
</main>
<script>
const JOBS = __DATA__;
const GENERATED = "__GENERATED__";
// Per-browser memory: when you last looked, and which postings you've applied to.
const store = {
  get(k, d){ try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v){ try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const LAST_VISIT = store.get("lastVisit", null);
const applied = new Set(store.get("applied", []));
addEventListener("pagehide", () => store.set("lastVisit", new Date().toISOString()));
const TABS = [["", "All roles"], ["swe", "SWE"], ["quant", "Quant"], ["finance", "Finance"],
              ["hardware", "Hardware"], ["events", "Events & programs"], ["other", "Other"]];
const fromHash = () => { const h = decodeURIComponent(location.hash.slice(1)); return TABS.some(t => t[0] === h) ? h : ""; };
const state = {win: LAST_VISIT ? "new" : "24", us: "1", sp: "", sec: fromHash(), st: "todo", page: 1};
const PAGE_SIZE = 50;
const SECTION = {swe: "SWE", quant: "Quant", finance: "Finance", hardware: "Hardware", events: "Event / program", other: "Other"};
const PLATFORM = {greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", workday: "Workday", oracle: "Oracle",
  eightfold: "Eightfold", workable: "Workable", rippling: "Rippling", pinpoint: "Pinpoint", page: "careers page"};
const sourceLabel = j => j.platform === "simplify"
  ? "via " + (j.source || (String(j.url).includes("vansh") ? "vanshb03" : "Simplify"))
  : "company site · " + (PLATFORM[j.platform] || j.platform);
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
// New = found by the tracker after your last visit (or in the last 24h on a first visit),
// skipping each source's first-run baseline so a newly added company doesn't flood it.
const isNew = j => !!j.first_seen && !j.baseline &&
  (LAST_VISIT ? new Date(j.first_seen) > new Date(LAST_VISIT) : Date.now() - new Date(j.first_seen) < 864e5);
const inWindow = j => state.win === "new" ? isNew(j) : (!state.win || ageHours(j.posted) <= +state.win);
const inTab = (j, sec) => sec ? j.section === sec : j.section !== "other";
function render(){
  const q = document.getElementById("q").value.toLowerCase();
  // Everything except the tab, so each tab can show how many postings it holds.
  const base = JOBS.filter(j =>
      (!state.us || j.us) &&
      inWindow(j) &&
      (!state.sp || j.sponsorship === state.sp) &&
      (state.st === "todo" ? !applied.has(j.url) : state.st === "done" ? applied.has(j.url) : true) &&
      (j.title + " " + j.company + " " + j.location).toLowerCase().includes(q));
  document.getElementById("tabs").innerHTML = TABS.map(([k, label]) =>
    `<a class="tab" href="#${k}" ${state.sec === k ? 'aria-current="page"' : ""}>${esc(label)}<span class="n">${base.filter(j => inTab(j, k)).length}</span></a>`).join("");
  const list = base.filter(j => inTab(j, state.sec))
    .sort((a, b) => sortKey === "posted"
      ? (Math.min(ageHours(a.posted), 1e9) - Math.min(ageHours(b.posted), 1e9)) * -sortDir  // smaller age = newer
      : String(a[sortKey] ?? "").localeCompare(String(b[sortKey] ?? "")) * sortDir);
  const pages = Math.max(1, Math.ceil(list.length / PAGE_SIZE));
  state.page = Math.min(state.page, pages);
  const shown = list.slice((state.page - 1) * PAGE_SIZE, state.page * PAGE_SIZE);
  document.getElementById("rows").innerHTML = shown.map(j => `<tr>
    <td class="co">${esc(j.company)}<br><small class="src">${esc(SECTION[j.section] || "")} · ${esc(sourceLabel(j))}</small></td>
    <td class="role"><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a>${isNew(j) ? '<span class="badge new">NEW</span>' : ""}</td>
    <td class="loc">${esc(j.location)}</td>
    <td class="when">${when(j.posted)}</td>
    <td class="spon"><span class="badge ${esc((j.sponsorship || "Not").split(" ")[0])}">${esc(j.sponsorship || "Not specified")}</span>
      ${j.sponsorship_evidence ? `<details><summary>Why?</summary>“${esc(j.sponsorship_evidence)}”</details>` : ""}</td>
    <td class="apcell"><input type="checkbox" class="ap" data-url="${esc(j.url)}" ${applied.has(j.url) ? "checked" : ""} aria-label="Applied"></td></tr>`).join("");
  renderPager(pages);
  const empty = document.getElementById("empty");
  empty.hidden = list.length > 0;
  empty.textContent = state.win === "new" ? "Nothing new since your last visit. Try Last 24 hours or 3 days."
    : state.win ? "Nothing posted in this window yet. Try 3 days or 7 days." : "No postings match.";
  const c = s => list.filter(j => j.sponsorship === s).length;
  const from = list.length ? (state.page - 1) * PAGE_SIZE + 1 : 0, to = Math.min(state.page * PAGE_SIZE, list.length);
  document.getElementById("sub").textContent = `${from}–${to} of ${list.length} matching (${JOBS.length} tracked) · ${c("Sponsors")} sponsor · ${c("Does not sponsor")} don't · ${c("Not specified")} not specified · updated ${new Date(GENERATED).toLocaleString()}`;
}
function renderPager(pages){
  const p = state.page, nums = new Set([1, pages, p - 1, p, p + 1].filter(n => n >= 1 && n <= pages));
  let html = `<button data-p="${p - 1}" ${p === 1 ? "disabled" : ""} aria-label="Previous page">‹ Prev</button>`, last = 0;
  for (const n of [...nums].sort((a, b) => a - b)) {
    if (n - last > 1) html += "<span>…</span>";
    html += `<button data-p="${n}" ${n === p ? 'aria-current="page"' : ""}>${n}</button>`; last = n;
  }
  html += `<button data-p="${p + 1}" ${p === pages ? "disabled" : ""} aria-label="Next page">Next ›</button>`;
  const el = document.getElementById("pager"); el.innerHTML = html; el.hidden = pages <= 1;
}
document.getElementById("pager").addEventListener("click", e => {
  const b = e.target.closest("button[data-p]"); if (!b || b.disabled) return;
  state.page = +b.dataset.p; render();
  document.getElementById("tabs").scrollIntoView({block: "start"});
});
function sync(){ document.querySelectorAll(".chip").forEach(b => b.setAttribute("aria-pressed", state[b.dataset.g] === b.dataset.v)); }
addEventListener("hashchange", () => { state.sec = fromHash(); state.page = 1; render(); });
document.getElementById("q").addEventListener("input", () => { state.page = 1; render(); });
document.getElementById("rows").addEventListener("change", e => {
  if (!e.target.classList.contains("ap")) return;
  e.target.checked ? applied.add(e.target.dataset.url) : applied.delete(e.target.dataset.url);
  store.set("applied", [...applied]);
});
document.querySelectorAll(".chip").forEach(b => b.addEventListener("click", () => { state[b.dataset.g] = b.dataset.v; state.page = 1; sync(); render(); }));
document.querySelectorAll("th[data-k]").forEach(th => th.addEventListener("click", () => {
  sortDir = sortKey === th.dataset.k ? -sortDir : (th.dataset.k === "posted" ? -1 : 1);
  sortKey = th.dataset.k; state.page = 1;
  document.querySelectorAll("th").forEach(x => x.removeAttribute("data-dir"));
  th.dataset.dir = sortDir > 0 ? "asc" : "desc"; render();
}));
sync(); render();
</script></body></html>
"""


def write(jobs):
    from db import now
    rows = [{k: j.get(k) for k in ("company", "platform", "title", "location", "url", "us", "posted",
                                   "first_seen", "sponsorship", "sponsorship_evidence", "section", "baseline", "source")}
            for j in jobs]
    data = json.dumps(rows).replace("</", "<\\/")  # keep job text from closing the <script> tag
    REPORT_PATH.write_text(PAGE.replace("__DATA__", data).replace("__GENERATED__", now()))


if __name__ == "__main__":
    import db
    conn = db.connect()
    write(db.all_jobs(conn))
    conn.close()
    subprocess.run(["open", str(REPORT_PATH)])
