"""Renders the daily report page and the archive index as static HTML."""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
REPORTS = DOCS / "reports"
MANIFEST = REPORTS / "manifest.json"

KIND_LABEL = {"blog": "Blog", "question": "Question", "discussion": "Discussion",
              "news": "News", "release": "Release", "other": "Item"}

CSS = """
:root{--paper:#F5F7F9;--surface:#FFFFFF;--ink:#16202A;--muted:#57636F;--rule:#D5DCE3;
--blue:#0B5FAE;--amber:#8F5A00;--amber-bg:#FFF1D6;--chip:#E8EEF4;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#0F1720;--surface:#16212C;
--ink:#E6EDF3;--muted:#9AA7B4;--rule:#2A3744;--blue:#7DBBF7;--amber:#F2B955;--amber-bg:#2F2610;--chip:#1F2C39}}
:root[data-theme="dark"]{--paper:#0F1720;--surface:#16212C;--ink:#E6EDF3;--muted:#9AA7B4;--rule:#2A3744;
--blue:#7DBBF7;--amber:#F2B955;--amber-bg:#2F2610;--chip:#1F2C39}
:root{box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}
*,*::before,*::after{box-sizing:inherit}
html{scroll-padding-top:calc(env(safe-area-inset-top,0px) + 4rem)}
body{margin:0;background:var(--paper);color:var(--ink);
font:1.0625rem/1.6 "IBM Plex Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:46rem;margin:0 auto;padding:0 1.25rem}
a{color:var(--blue)}a:focus-visible,button:focus-visible,summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
h1,h2,h3{font-family:"IBM Plex Serif",Georgia,"Times New Roman",serif;line-height:1.25}
header.mast{padding:3rem 0 1.5rem}
.kicker{color:var(--muted);margin:0 0 .25rem;font-size:.95rem}
h1{font-size:clamp(2rem,6vw,3rem);margin:0 0 1rem;font-weight:600;letter-spacing:-.01em}
.lead{font-family:"IBM Plex Serif",Georgia,serif;font-size:1.3rem;line-height:1.45;margin:0 0 1rem}
.stats{color:var(--muted);margin:0}
nav.toc{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--paper);
border-bottom:1px solid var(--rule);overflow-x:auto;white-space:nowrap}
nav.toc .wrap{display:flex;gap:1.25rem;padding-top:.7rem;padding-bottom:.7rem}
nav.toc a{text-decoration:none;color:var(--ink);font-size:.95rem}
nav.toc a:hover{color:var(--blue)}
section{padding:2.25rem 0 .5rem}
h2{font-size:1.6rem;margin:0 0 .35rem}
.sub{color:var(--muted);margin:0 0 1.25rem}
.story{background:var(--surface);border:1px solid var(--rule);border-radius:10px;padding:1.1rem 1.25rem;margin:0 0 1rem}
.story h3{margin:.1rem 0 .5rem;font-size:1.2rem}
.story p{margin:.5rem 0}
.prio{display:inline-block;font-size:.8rem;font-weight:600;color:var(--amber);background:var(--amber-bg);
border-radius:4px;padding:.1rem .45rem}
.why{color:var(--ink)}.why strong{font-weight:600}
.src{font-size:.9rem;color:var(--muted);margin-top:.6rem}
.src a{display:inline-block;margin:0 .9rem .3rem 0}
.plain{border-left:3px solid var(--rule);padding:.1rem 0 .1rem 1rem;margin:0 0 1.25rem}
.plain h3{margin:0 0 .35rem;font-size:1.1rem}
.plain p{margin:.35rem 0}
.dive{margin:0 0 2rem}
.dive h3{font-size:1.35rem;margin:0 0 .5rem}
.chips{display:flex;flex-wrap:wrap;gap:.4rem;margin:.75rem 0 0;padding:0;list-style:none}
.chips li{background:var(--chip);border-radius:4px;padding:.15rem .5rem;font-size:.88rem}
code{font-family:ui-monospace,"SFMono-Regular",Consolas,monospace;font-size:.92em;background:var(--chip);
padding:.05rem .3rem;border-radius:3px}
.draft{background:var(--surface);border:1px solid var(--rule);border-radius:10px;margin:0 0 1.25rem;overflow:hidden}
.draft-head{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.75rem 1rem;
border-bottom:1px solid var(--rule)}
.draft-head h3{margin:0;font-size:1.05rem}
.draft pre{margin:0;padding:1rem;white-space:pre-wrap;word-wrap:break-word;font:inherit;line-height:1.55}
button.copy{font:inherit;font-size:.9rem;background:var(--blue);color:#fff;border:0;border-radius:6px;
padding:.4rem .85rem;cursor:pointer;flex:none}
:root[data-theme="dark"] button.copy{color:#0F1720}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) button.copy{color:#0F1720}}
details{border-top:1px solid var(--rule);padding:.6rem 0}
details:last-of-type{border-bottom:1px solid var(--rule)}
summary{cursor:pointer;font-weight:600}
summary .n{color:var(--muted);font-weight:400}
.idx{list-style:none;margin:.6rem 0 0;padding:0}
.idx li{padding:.45rem 0;border-top:1px dashed var(--rule)}
.idx li:first-child{border-top:0}
.kind{color:var(--muted);font-size:.85rem;margin-right:.4rem}
.one{display:block;color:var(--muted);font-size:.93rem}
.oos{opacity:.8}
footer{color:var(--muted);font-size:.9rem;padding:3rem 0 2.5rem}
.archive li{padding:.9rem 0;border-bottom:1px solid var(--rule);list-style:none}
.archive{padding:0}.archive a{font-family:"IBM Plex Serif",Georgia,serif;font-size:1.2rem}
.archive p{margin:.25rem 0 0;color:var(--muted)}
.empty{color:var(--muted);font-style:italic}
@media (prefers-reduced-motion:no-preference){.story,.dive{scroll-margin-top:4rem}}
"""

HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📡</text></svg>">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Serif:wght@400;600&display=swap" rel="stylesheet">
<style>{css}</style></head><body>"""

COPY_JS = """<script>
document.querySelectorAll('button.copy').forEach(function(b){b.addEventListener('click',function(){
var t=document.getElementById(b.dataset.target).innerText;
navigator.clipboard.writeText(t).then(function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy text'},2000)},
function(){b.textContent='Select and copy manually'})})});
</script>"""


def e(text):
    return html.escape(str(text or ""))


def rich(text):
    """Escape, then allow `code`, **bold** and paragraph breaks."""
    out = []
    for para in re.split(r"\n\s*\n", str(text or "").strip()):
        p = e(para)
        p = re.sub(r"`([^`]+)`", r"<code>\1</code>", p)
        p = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", p)
        out.append("<p>" + p.replace("\n", "<br>") + "</p>")
    return "".join(out)


def sources(refs, items):
    links = []
    for r in refs or []:
        if isinstance(r, int) and 0 <= r < len(items) and items[r].get("link"):
            it = items[r]
            label = KIND_LABEL.get(it["kind"], "Item")
            links.append(f'<a href="{e(it["link"])}" title="{e(it["title"])}">{label}: {e(it["title"][:60])}</a>')
    return f'<div class="src">{"".join(links)}</div>' if links else ""


def render_daily(date_iso, date_label, digest, items, triage, deep_refs, generated_at):
    in_scope = sum(1 for t in triage.values() if t.get("in_scope"))
    parts = [HEAD.format(title=e(f"SAP Community digest · {date_label}"), css=CSS)]

    parts.append(f"""<header class="mast"><div class="wrap">
<p class="kicker">SAP Community daily digest</p><h1>{e(date_label)}</h1>
<p class="lead">{e(digest.get("headline"))}</p>
<p class="stats">Screened {len(items)} new items from the last day. {in_scope} were technical, and {len(deep_refs)} were read in full.</p>
</div></header>
<nav class="toc" aria-label="Sections"><div class="wrap">
<a href="#overview">Overview</a><a href="#top">Top stories</a><a href="#releases">Releases</a>
<a href="#dives">Deep dives</a><a href="#problems">Developer problems</a><a href="#drafts">Post drafts</a><a href="#all">Everything</a>
</div></nav><main class="wrap">""")

    parts.append(f'<section id="overview"><h2>The day in one minute</h2>{rich(digest.get("overview"))}</section>')

    parts.append('<section id="top"><h2>Top stories</h2><p class="sub">Ranked by how much they matter to ABAP developers.</p>')
    stories = sorted(digest.get("top_stories", []), key=lambda s: s.get("priority", 3))
    for s in stories:
        parts.append(f"""<article class="story"><span class="prio">Priority {int(s.get("priority", 3))}</span>
<h3>{e(s.get("title"))}</h3>{rich(s.get("summary"))}
<p class="why"><strong>Why it matters:</strong> {e(s.get("why_it_matters"))}</p>{sources(s.get("refs"), items)}</article>""")
    if not stories:
        parts.append('<p class="empty">No major stories today.</p>')
    parts.append("</section>")

    parts.append('<section id="releases"><h2>Releases and announcements</h2>')
    rel = digest.get("releases", [])
    for r in rel:
        parts.append(f'<div class="plain"><h3>{e(r.get("title"))}</h3>{rich(r.get("summary"))}{sources(r.get("refs"), items)}</div>')
    if not rel:
        parts.append('<p class="empty">Nothing new was released or announced today.</p>')
    parts.append("</section>")

    parts.append('<section id="dives"><h2>Deep dives</h2><p class="sub">The most valuable technical posts, explained.</p>')
    for d in digest.get("deep_dives", []):
        chips = "".join(f"<li>{e(c)}</li>" for c in d.get("key_concepts", []))
        parts.append(f"""<article class="dive"><h3>{e(d.get("title"))}</h3>{rich(d.get("explanation"))}
{f'<ul class="chips" aria-label="Key concepts">{chips}</ul>' if chips else ""}{sources(d.get("refs"), items)}</article>""")
    parts.append("</section>")

    parts.append('<section id="problems"><h2>What developers are struggling with</h2>'
                 '<p class="sub">Patterns from today\'s questions. Useful for classes and interview prep.</p>')
    probs = digest.get("trending_problems", [])
    for p in probs:
        parts.append(f"""<div class="plain"><h3>{e(p.get("theme"))}</h3>{rich(p.get("description"))}
<p><strong>Teaching tip:</strong> {e(p.get("teaching_tip"))}</p>{sources(p.get("refs"), items)}</div>""")
    if not probs:
        parts.append('<p class="empty">No clear patterns in today\'s questions.</p>')
    parts.append("</section>")

    parts.append('<section id="drafts"><h2>Post drafts for your community</h2>'
                 '<p class="sub">Ready to copy into WhatsApp. Review before posting.</p>')
    for n, dr in enumerate(digest.get("post_drafts", [])):
        parts.append(f"""<div class="draft"><div class="draft-head"><h3>{e(dr.get("title"))}</h3>
<button class="copy" type="button" data-target="draft{n}">Copy text</button></div>
<pre id="draft{n}">{e(dr.get("text"))}</pre></div>""")
    parts.append("</section>")

    parts.append('<section id="all"><h2>Everything from today</h2>'
                 '<p class="sub">Every item collected, grouped by area. Items outside your focus areas are dimmed.</p>')
    groups = {}
    for i, it in enumerate(items):
        t = triage.get(i, {})
        groups.setdefault(t.get("category", "Other"), []).append((i, it, t))
    for cat in sorted(groups, key=lambda c: -len(groups[c])):
        rows = sorted(groups[cat], key=lambda x: -x[2].get("importance", 1))
        lis = []
        for i, it, t in rows:
            cls = "" if t.get("in_scope") else ' class="oos"'
            lis.append(f"""<li{cls}><span class="kind">{KIND_LABEL.get(it["kind"], "Item")}</span>
<a href="{e(it["link"])}">{e(it["title"])}</a><span class="one">{e(t.get("one_liner", ""))}</span></li>""")
        parts.append(f'<details><summary>{e(cat)} <span class="n">({len(rows)})</span></summary><ul class="idx">{"".join(lis)}</ul></details>')
    parts.append("</section>")

    parts.append(f"""</main><footer><div class="wrap">Generated {e(generated_at)}. Summaries are written by Claude;
check the original post before quoting or teaching from it. <a href="../index.html">All reports</a></div></footer>{COPY_JS}</body></html>""")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{date_iso}.html").write_text("".join(parts), encoding="utf-8")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else []
    manifest = [m for m in manifest if m["date"] != date_iso]
    manifest.append({"date": date_iso, "label": date_label, "headline": digest.get("headline", ""),
                     "items": len(items), "deep": len(deep_refs)})
    manifest.sort(key=lambda m: m["date"], reverse=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    render_index(manifest)


def render_index(manifest):
    rows = "".join(f"""<li><a href="reports/{e(m["date"])}.html">{e(m["label"])}</a>
<p>{e(m["headline"])}</p><p>{m["items"]} items screened, {m["deep"]} read in full.</p></li>""" for m in manifest)
    page = HEAD.format(title="SAP Community daily digest", css=CSS) + f"""
<header class="mast"><div class="wrap"><p class="kicker">Archive</p><h1>SAP Community daily digest</h1>
<p class="lead">A daily deep read of everything new in SAP Community, written for ABAP developers.</p></div></header>
<main class="wrap"><ul class="archive">{rows or '<li class="empty">The first report will appear after tomorrow morning\'s run.</li>'}</ul></main>
<footer><div class="wrap">Updated automatically every morning.</div></footer></body></html>"""
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "index.html").write_text(page, encoding="utf-8")
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")
