"""Renders the daily SAP job market report under docs/jobs/."""
import json

from sapdigest.report import CSS, DOCS, HEAD, e, rich

JOBS_DIR = DOCS / "jobs"
MANIFEST = JOBS_DIR / "manifest.json"

EXTRA_CSS = """
.jobcard{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:1rem 1.2rem;margin:0 0 .9rem}
.jobcard h3{margin:.35rem 0 .2rem;font-size:1.15rem}
.jobcard h3 a{color:var(--ink);text-decoration:none}.jobcard h3 a:hover{color:var(--blue);text-decoration:underline}
.meta{color:var(--muted);font-size:.93rem;margin:0}
.reason{margin:.5rem 0 0;font-size:.95rem}
.bars{list-style:none;margin:0;padding:0}
.bars li{display:grid;grid-template-columns:minmax(9rem,15rem) 1fr auto;gap:.8rem;align-items:center;padding:.35rem 0;
border-top:1px dashed var(--rule)}
.bars li:first-child{border-top:0}
.track{display:block;background:var(--chip);border-radius:3px;height:.7rem;overflow:hidden}
.fill{display:block;background:var(--blue);height:100%;border-radius:3px}
.num{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.9rem;white-space:nowrap}
.companies{columns:2 14rem;padding-left:1.2rem}.companies li{margin:.2rem 0}
.srcs{list-style:none;padding:0}.srcs li{padding:.3rem 0;border-top:1px dashed var(--rule)}
.srcs .bad{color:var(--amber)}
ul.plainlist{padding-left:1.2rem}ul.plainlist li{margin:.35rem 0}
@media (max-width:34rem){.bars li{grid-template-columns:1fr auto}.bars .track{grid-column:1 / -1;grid-row:2}}
"""


def _card(j):
    chips = "".join(f"<li>{e(s)}</li>" for s in j.get("skills", []))
    meta = " · ".join(x for x in [j["company"], j["location"], j.get("experience"), j.get("work_mode"), j.get("salary")]
                      if x and x != "Not stated")
    link = f'<a href="{e(j["url"])}">{e(j["title"])}</a>' if j.get("url") else e(j["title"])
    return f"""<article class="jobcard"><span class="prio">Match {int(j.get("match", 0))}/5</span>
<h3>{link}</h3><p class="meta">{e(meta)}</p>
{f'<ul class="chips">{chips}</ul>' if chips else ""}
<p class="reason">{e(j.get("match_reason", ""))}</p><p class="meta">Source: {e(j["source"])}{f" · Posted {e(j['posted'])}" if j.get("posted") else ""}</p></article>"""


def render(date_iso, date_label, sap_jobs, all_jobs, coverage, trends, days, companies, summary, generated):
    s = summary or {}
    headline = s.get("headline") or (f"{len(sap_jobs)} new SAP technical roles found today."
                                     if sap_jobs else "No new SAP technical roles were found today.")
    p = [HEAD.format(title=e(f"SAP job market · {date_label}"), css=CSS + EXTRA_CSS)]
    p.append(f"""<header class="mast"><div class="wrap"><p class="kicker">SAP job market</p><h1>{e(date_label)}</h1>
<p class="lead">{e(headline)}</p>
<p class="stats">{len(all_jobs)} new postings checked, {len(sap_jobs)} are SAP technical roles.</p></div></header>
<nav class="toc" aria-label="Sections"><div class="wrap"><a href="#summary">Summary</a><a href="#matches">Best matches</a>
<a href="#skills">Skills in demand</a><a href="#companies">Top companies</a><a href="#all">All new roles</a><a href="#sources">Sources</a>
</div></nav><main class="wrap">""")

    p.append('<section id="summary"><h2>Market summary</h2>')
    if s:
        p.append(rich(s.get("market_summary")))
        if s.get("skill_insights"):
            p.append("<h3>What the skill data says</h3><ul class=\"plainlist\">" +
                     "".join(f"<li>{e(x)}</li>" for x in s["skill_insights"]) + "</ul>")
        if s.get("teaching_insights"):
            p.append("<h3>For your training</h3><ul class=\"plainlist\">" +
                     "".join(f"<li>{e(x)}</li>" for x in s["teaching_insights"]) + "</ul>")
        if s.get("advice"):
            p.append(f"<h3>For your own search</h3>{rich(s['advice'])}")
    else:
        p.append('<p class="empty">No summary today. See the sections below for the raw data.</p>')
    p.append("</section>")

    best = sorted([j for j in sap_jobs if j.get("match", 0) >= 4], key=lambda j: -j.get("match", 0))[:12]
    p.append('<section id="matches"><h2>Best matches for you</h2><p class="sub">Roles scoring 4 or 5 against your profile.</p>')
    p.extend(_card(j) for j in best)
    if not best:
        p.append('<p class="empty">No strong matches among today\'s new roles.</p>')
    p.append("</section>")

    p.append('<section id="skills"><h2>Skills in demand</h2>')
    note = ("Counts are from new SAP technical roles over the last 7 days, compared with the 7 days before."
            if days >= 7 else f"Only {days} day{'s' if days != 1 else ''} of data so far. Week-on-week trends "
            "become meaningful after two weeks of daily runs.")
    p.append(f'<p class="sub">{e(note)}</p>')
    if trends:
        top = max(r["this_week"] for r in trends) or 1
        rows = []
        for r in trends:
            diff = r["this_week"] - r["last_week"]
            change = "" if not r["last_week"] else (f", up {diff}" if diff > 0 else f", down {-diff}" if diff < 0 else ", same")
            rows.append(f"""<li><span>{e(r["skill"])}</span><span class="track"><span class="fill" style="width:{100 * r["this_week"] / top:.0f}%"></span></span>
<span class="num">{r["this_week"]} this week{change}</span></li>""")
        p.append(f'<ul class="bars">{"".join(rows)}</ul>')
    else:
        p.append('<p class="empty">No skill data yet.</p>')
    p.append("</section>")

    p.append('<section id="companies"><h2>Top hiring companies today</h2>')
    if companies:
        p.append('<ol class="companies">' + "".join(f"<li>{e(c)} <span class=\"num\">({n})</span></li>"
                                                    for c, n in companies) + "</ol>")
    else:
        p.append('<p class="empty">No company data today.</p>')
    p.append("</section>")

    p.append('<section id="all"><h2>All new SAP technical roles</h2><p class="sub">Grouped by role type, best matches first.</p>')
    groups = {}
    for j in sap_jobs:
        groups.setdefault(j.get("role", "Other SAP"), []).append(j)
    for role in sorted(groups, key=lambda r: -len(groups[r])):
        rows = sorted(groups[role], key=lambda j: -j.get("match", 0))
        lis = "".join(f"""<li><span class="kind">Match {int(j.get("match", 0))}/5</span>
<a href="{e(j["url"])}">{e(j["title"])}</a><span class="one">{e(" · ".join(x for x in [j["company"], j["location"], j.get("experience")] if x and x != "Not stated"))}</span></li>"""
                      for j in rows)
        p.append(f'<details><summary>{e(role)} <span class="n">({len(rows)})</span></summary><ul class="idx">{lis}</ul></details>')
    other = [j for j in all_jobs if not j.get("sap_technical")]
    if other:
        lis = "".join(f'<li><a href="{e(j["url"])}">{e(j["title"])}</a><span class="one">{e(j["company"])} · {e(j.get("role", ""))}</span></li>'
                      for j in other)
        p.append(f'<details><summary>Other postings, not SAP technical <span class="n">({len(other)})</span></summary><ul class="idx oos">{lis}</ul></details>')
    if not sap_jobs:
        p.append('<p class="empty">No new SAP technical roles today.</p>')
    p.append("</section>")

    p.append('<section id="sources"><h2>Sources checked</h2><ul class="srcs">' + "".join(
        f'<li><strong>{e(k)}:</strong> <span class="{"bad" if str(v).startswith("failed") else ""}">{e(v)}</span></li>'
        for k, v in coverage.items()) + "</ul></section>")

    p.append(f"""</main><footer><div class="wrap">Generated {e(generated)}. Job details come from the listed sources and
are analysed by Claude; always check the original posting. <a href="index.html">All job reports</a> ·
<a href="../index.html">SAP Community digest</a></div></footer></body></html>""")

    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    (JOBS_DIR / f"{date_iso}.html").write_text("".join(p), encoding="utf-8")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    manifest = [m for m in manifest if m["date"] != date_iso]
    manifest.append({"date": date_iso, "label": date_label, "headline": headline, "sap": len(sap_jobs)})
    manifest.sort(key=lambda m: m["date"], reverse=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = "".join(f"""<li><a href="{e(m["date"])}.html">{e(m["label"])}</a><p>{e(m["headline"])}</p>
<p>{m["sap"]} new SAP technical roles.</p></li>""" for m in manifest)
    (JOBS_DIR / "index.html").write_text(HEAD.format(title="SAP job market", css=CSS) + f"""
<header class="mast"><div class="wrap"><p class="kicker">Archive</p><h1>SAP job market</h1>
<p class="lead">Daily new SAP technical roles, skill demand and hiring companies.</p></div></header>
<main class="wrap"><ul class="archive">{rows}</ul></main>
<footer><div class="wrap"><a href="../index.html">SAP Community digest</a></div></footer></body></html>""", encoding="utf-8")
