#!/usr/bin/env python3
"""Daily SAP Community deep-research digest.

Stage 1  Triage:     Claude (fast model) classifies EVERY collected item.
Stage 2  Deep read:  Claude (fast model) reads the most important items in full.
Stage 3  Synthesis:  Claude (deep model) writes the day's analysis.
Then:    HTML report is written to docs/, and the highlights go to WhatsApp.

Claude runs through Claude Code on your Claude subscription (see sapdigest/llm.py).

Usage:
  python digest.py                  full run
  python digest.py --no-whatsapp    build the report only
  python digest.py --send-only      send today's already-built report to WhatsApp
  python digest.py --test-whatsapp  send Meta's hello_world test message and stop
"""
import argparse
import datetime as dt
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from sapdigest import feeds, llm, report, whatsapp

ROOT = Path(__file__).resolve().parent

CATEGORIES = [
    "ABAP & Clean Code", "RAP", "CDS & Data Modeling", "S/4HANA Development & Extensibility",
    "BTP & ABAP Cloud", "OData, APIs & Integration", "Fiori & UI5", "HANA, AMDP & Performance",
    "Developer Tools & DevOps", "AI & Joule", "Security & Basis", "Functional & Business Processes",
    "Analytics & Data", "Community, Events & Careers", "Other",
]

TRIAGE_SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "i": {"type": "integer", "description": "The item's index exactly as given"},
            "category": {"type": "string", "enum": CATEGORIES},
            "in_scope": {"type": "boolean", "description": "True if it matches the reader's focus areas"},
            "importance": {"type": "integer", "minimum": 1, "maximum": 5,
                           "description": "5 = must-know for ABAP developers today, 1 = noise"},
            "one_liner": {"type": "string", "description": "Plain, specific 1-sentence summary, max 25 words"},
        },
        "required": ["i", "category", "in_scope", "importance", "one_liner"],
    }}},
    "required": ["items"],
}

ANALYSIS_FIELDS = {
    "ref": {"type": "integer", "description": "The post's ref number exactly as given"},
    "summary": {"type": "string", "description": "3-5 sentences on what the post actually says"},
    "key_points": {"type": "array", "items": {"type": "string"}, "maxItems": 6},
    "technical_details": {"type": "array", "items": {"type": "string"}, "maxItems": 8,
                          "description": "Concrete objects, syntax, annotations, releases, SAP notes, versions"},
    "why_it_matters": {"type": "string"},
    "is_release_or_announcement": {"type": "boolean"},
    "developer_problem": {"type": "string",
                          "description": "For questions: the underlying problem in one sentence. Empty otherwise."},
    "teaching_angle": {"type": "string", "description": "How a trainer could use this in a class or interview prep"},
    "quality": {"type": "integer", "minimum": 1, "maximum": 5,
                "description": "Technical depth and accuracy of the source itself"},
}
DEEP_SCHEMA = {
    "type": "object",
    "properties": {"analyses": {"type": "array", "items": {
        "type": "object", "properties": ANALYSIS_FIELDS, "required": list(ANALYSIS_FIELDS)}}},
    "required": ["analyses"],
}

REFS = {"type": "array", "items": {"type": "integer"}, "description": "ref numbers of the source items"}
SYNTH_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sentence capturing the day, max 25 words"},
        "overview": {"type": "string", "description": "2 short paragraphs: what happened and what it means"},
        "top_stories": {"type": "array", "maxItems": 10, "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "summary": {"type": "string"}, "why_it_matters": {"type": "string"},
            "priority": {"type": "integer", "minimum": 1, "maximum": 3}, "refs": REFS},
            "required": ["title", "summary", "why_it_matters", "priority", "refs"]}},
        "releases": {"type": "array", "items": {"type": "object", "properties": {
            "title": {"type": "string"}, "summary": {"type": "string"}, "refs": REFS},
            "required": ["title", "summary", "refs"]}},
        "deep_dives": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
            "title": {"type": "string"},
            "explanation": {"type": "string", "description": "3-5 paragraphs; use `backticks` for code and object names"},
            "key_concepts": {"type": "array", "items": {"type": "string"}}, "refs": REFS},
            "required": ["title", "explanation", "key_concepts", "refs"]}},
        "trending_problems": {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "theme": {"type": "string"}, "description": {"type": "string"},
            "teaching_tip": {"type": "string"}, "refs": REFS},
            "required": ["theme", "description", "teaching_tip", "refs"]}},
        "post_drafts": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
            "title": {"type": "string"},
            "text": {"type": "string", "description": "WhatsApp-ready post. *bold* for emphasis, short lines, source link at the end"}},
            "required": ["title", "text"]}},
        "interview_questions": {"type": "array", "maxItems": 3, "items": {"type": "object", "properties": {
            "question": {"type": "string"}, "answer": {"type": "string"},
            "level": {"type": "string", "enum": ["Mid-level", "Senior", "Architect"]}, "refs": REFS},
            "required": ["question", "answer", "level", "refs"]}},
        "class_idea": {"type": "object", "properties": {
            "title": {"type": "string"},
            "why_now": {"type": "string", "description": "Why this topic is timely, based on today's material"},
            "outline": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "exercise": {"type": "string", "description": "One hands-on exercise students can do in ADT"},
            "refs": REFS},
            "required": ["title", "why_now", "outline", "exercise", "refs"]},
        "whatsapp_highlights": {"type": "string",
                                "description": "Top 3-4 stories on ONE line, separated by ' | ', max 600 characters"},
    },
    "required": ["headline", "overview", "top_stories", "releases", "deep_dives",
                 "trending_problems", "post_drafts", "interview_questions", "class_idea",
                 "whatsapp_highlights"],
}


def load_config():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def focus_text(cfg):
    return "\n".join(f"- {a}" for a in cfg["scope"]["focus_areas"])


# ── Stage 1 ──────────────────────────────────────────────────────────────
def triage(items, cfg):
    system = (
        "You screen SAP Community content for this reader:\n" + cfg["audience"] +
        "\nTheir focus areas:\n" + focus_text(cfg) +
        "\nClassify every item you are given. Never skip an item.\n\n"
        "in_scope rules (be strict): true ONLY when the item is about building, extending, debugging, "
        "testing or tuning software: ABAP code, RAP, CDS, OData/API development, integration development, "
        "Fiori/UI5 development, BTP/CAP development, developer tools, SQL/performance, or AI used by developers. "
        "false for functional configuration, customizing, master data, business process questions, migration "
        "planning, HR/finance/logistics setup, licensing, events, marketing and career posts, even when they "
        "appear in a technical forum or mention S/4HANA.\n\n"
        "Importance: new features, breaking changes, deprecations, security issues, deep how-tos with real code "
        "and common hard problems rank high; marketing, event promos, vague or duplicate questions rank low.\n\n"
        "Category guide: 'ABAP & Clean Code' = ABAP language, classic reports, forms, enhancements, TMG. "
        "'RAP' = behavior definitions, actions, draft, BO implementation. 'CDS & Data Modeling' = CDS views, "
        "annotations, VDM, access control (not Datasphere or BW). 'S/4HANA Development & Extensibility' = BAdIs, "
        "custom fields, key-user and developer extensibility, clean core (not functional S/4 questions). "
        "'BTP & ABAP Cloud' = BTP ABAP environment, CAP, Cloud Foundry, ABAP Cloud rules. "
        "'OData, APIs & Integration' = OData, Gateway, APIs, CPI, Integration Suite. 'HANA, AMDP & Performance' = "
        "SQL, AMDP, runtime and DB performance. 'Security & Basis' = authorizations, SSO, system admin, EarlyWatch. "
        "'Analytics & Data' = BW, Datasphere, SAC, BDC. 'Functional & Business Processes' = configuration and "
        "business process questions of any module."
    )
    size = cfg["limits"]["triage_batch_size"]
    batches = [list(range(s, min(s + size, len(items)))) for s in range(0, len(items), size)]

    def run(batch):
        lines = [json.dumps({"i": i, "type": items[i]["kind"], "title": items[i]["title"],
                             "tags": items[i]["tags"][:6], "excerpt": items[i]["text"][:350]},
                            ensure_ascii=False) for i in batch]
        try:
            out = llm.call_tool(cfg["models"]["fast"], system,
                                f"Classify these {len(batch)} items:\n" + "\n".join(lines),
                                "record_triage", TRIAGE_SCHEMA)
            return out.get("items", [])
        except Exception as exc:
            print(f"Triage batch starting at {batch[0]} failed: {exc}")
            return []

    results = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows in pool.map(run, batches):
            for r in rows:
                if isinstance(r.get("i"), int) and 0 <= r["i"] < len(items):
                    results[r["i"]] = r
    for i, it in enumerate(items):
        results.setdefault(i, {"i": i, "category": "Other", "in_scope": True,
                               "importance": 2, "one_liner": it["title"]})
        if cfg["scope"]["mode"] == "everything":
            results[i]["in_scope"] = True
    return results


# ── Stage 2 ──────────────────────────────────────────────────────────────
def deep_read(items, tri, cfg):
    candidates = [i for i, t in tri.items() if t["in_scope"]]
    candidates.sort(key=lambda i: (-tri[i]["importance"], items[i]["kind"] == "question"))
    chosen = candidates[: cfg["limits"]["max_deep_reads"]]
    size = cfg["limits"].get("deep_batch_size", 6)
    batches = [chosen[s:s + size] for s in range(0, len(chosen), size)]
    system = (
        "You are a senior SAP ABAP architect reading SAP Community content for this reader:\n" + cfg["audience"] +
        "\nYou will get several posts. Analyse EACH one separately and return one analysis per post, "
        "using its ref number. Extract what is genuinely useful. Be concrete: name the objects, syntax, "
        "annotations, releases and versions involved. If a post is shallow or wrong, say so plainly. "
        "Do not invent details that are not in the text."
    )

    # Fetch full pages for short excerpts all at once, in parallel, before Claude starts reading.
    texts = {i: items[i]["text"] for i in chosen}
    short = [i for i in chosen if len(texts[i]) < 800 and items[i].get("link")]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i, fuller in zip(short, pool.map(lambda i: feeds.fetch_full_text(items[i]["link"]), short)):
            if len(fuller) > len(texts[i]):
                texts[i] = fuller

    def post_text(i):
        it = items[i]
        return (f"=== POST ref={i} ===\nType: {it['kind']}\nTitle: {it['title']}\n"
                f"Tags: {', '.join(it['tags'])}\n\n{texts[i][:6000]}\n")

    def run(batch):
        user = f"Analyse these {len(batch)} posts:\n\n" + "\n".join(post_text(i) for i in batch)
        try:
            out = llm.call_tool(cfg["models"]["fast"], system, user, "record_analysis", DEEP_SCHEMA)
            return out.get("analyses", [])
        except Exception as exc:
            print(f"Deep read batch {batch} failed: {exc}")
            return []

    results = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows in pool.map(run, batches):
            for a in rows:
                ref = a.pop("ref", None)
                if isinstance(ref, int) and ref in chosen:
                    results[ref] = a
    return results


# ── Stage 3 ──────────────────────────────────────────────────────────────
def synthesize(items, tri, deep, cfg, date_label):
    read = [{"ref": i, "type": items[i]["kind"], "title": items[i]["title"],
             "category": tri[i]["category"], "importance": tri[i]["importance"], **a}
            for i, a in deep.items()]
    others = [{"ref": i, "type": items[i]["kind"], "title": items[i]["title"],
               "category": tri[i]["category"], "one_liner": tri[i]["one_liner"]}
              for i, t in tri.items() if t["in_scope"] and i not in deep]
    system = (
        "You are the editor of a daily SAP intelligence briefing for this reader:\n" + cfg["audience"] +
        "\nWrite with the precision of a senior ABAP architect. Plain, direct English. No hype, "
        "no filler, no marketing tone. Every claim must come from the material provided; cite sources "
        "using their ref numbers. Group related items into one story instead of repeating them. "
        "Post drafts are for the reader's WhatsApp developer community: practical, accurate, "
        "5-12 short lines, one clear takeaway, *bold* for emphasis, and the source link at the end.\n\n"
        "Deep dives: at least two of the three must cover the core ABAP stack (ABAP language, RAP, CDS, "
        "SQL/AMDP/performance, enhancements, ADT). Prefer posts with concrete code or patterns over conceptual, "
        "marketing or vendor-announcement posts.\n\n"
        "Interview questions: write 3 questions an interviewer could ask an experienced ABAP developer, each "
        "grounded in today's material, with a model answer of 4-8 sentences that is technically precise.\n\n"
        "Class idea: propose one ready-to-teach topic for experienced ABAP developers based on today's material, "
        "preferably from what developers are struggling with, with a short outline and a hands-on exercise."
    )
    links = {i: items[i]["link"] for i in deep}
    user = (f"Date: {date_label}\nTotal items collected today: {len(items)}\n\n"
            f"ITEMS READ IN FULL:\n{json.dumps(read, ensure_ascii=False)}\n\n"
            f"OTHER RELEVANT ITEMS (headline only):\n{json.dumps(others, ensure_ascii=False)}\n\n"
            f"Links by ref for post drafts:\n{json.dumps(links)}\n\nWrite today's briefing.")
    return llm.call_tool(cfg["models"]["deep"], system, user, "publish_digest", SYNTH_SCHEMA)


def fallback_digest(items, tri):
    """Used if the synthesis call fails, so a report still goes out."""
    top = sorted(tri.values(), key=lambda t: -t["importance"])[:8]
    if llm.limit_reached():
        reason = ("Your Claude plan's usage limit was reached during this morning's run, so the full analysis "
                  "was skipped. Below are the highest-ranked items that were screened before the limit.")
    else:
        reason = ("The detailed analysis step failed today, so this report lists the highest-ranked items "
                  "from the quick screening. Check the workflow log on GitHub for the error.")
    return {
        "headline": "Today's items, ranked (the full analysis could not run)",
        "overview": reason,
        "top_stories": [{"title": items[t["i"]]["title"], "summary": t["one_liner"],
                         "why_it_matters": f"Ranked {t['importance']}/5 in screening.",
                         "priority": 1 if t["importance"] >= 4 else 2, "refs": [t["i"]]} for t in top],
        "releases": [], "deep_dives": [], "trending_problems": [], "post_drafts": [],
        "interview_questions": [], "class_idea": None,
        "whatsapp_highlights": " | ".join(items[t["i"]]["title"] for t in top[:4]),
    }


def site_url(cfg):
    if cfg["report"].get("site_url"):
        return cfg["report"]["site_url"].rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "your-user/your-repo")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-whatsapp", action="store_true")
    ap.add_argument("--send-only", action="store_true")
    ap.add_argument("--test-whatsapp", action="store_true")
    args = ap.parse_args()
    cfg = load_config()

    if args.test_whatsapp:
        whatsapp.send_hello_world(cfg)
        return

    tz = ZoneInfo(cfg["timezone"])
    now = dt.datetime.now(tz)
    date_iso, date_label = now.strftime("%Y-%m-%d"), now.strftime("%A, %-d %B %Y")
    url = f"{site_url(cfg)}/reports/{date_iso}.html"

    if args.send_only:
        saved = feeds.load_json(ROOT / "data" / "archive" / f"{date_iso}.json", None)
        if not saved:
            raise SystemExit(f"No report built for {date_iso}; run without --send-only first.")
        whatsapp.send_digest(cfg, date_label, saved["digest"].get("whatsapp_highlights", ""), url)
        return

    feeds.collect(cfg)  # catch anything posted since the last collection run
    items = feeds.load_json(feeds.QUEUE, [])
    print(f"Processing {len(items)} items for {date_label}")
    if not items:
        digest, tri, deep = {"headline": "A quiet day: nothing new was collected.",
                             "overview": "No new items were found in the feeds since the last report.",
                             "whatsapp_highlights": "No new SAP Community activity was collected."}, {}, {}
    else:
        tri = triage(items, cfg)
        print(f"Triage done: {sum(t['in_scope'] for t in tri.values())} in scope")
        deep = deep_read(items, tri, cfg)
        print(f"Deep read done: {len(deep)} items")
        try:
            digest = synthesize(items, tri, deep, cfg, date_label)
        except Exception as exc:
            print(f"Synthesis failed: {exc}")
            digest = fallback_digest(items, tri)

    generated = now.strftime("%-d %b %Y, %H:%M %Z")
    report.render_daily(date_iso, date_label, digest, items, tri, list(deep), generated)
    print(f"Report written: {url}")

    feeds.save_json(ROOT / "data" / "archive" / f"{date_iso}.json",
                    {"items": items, "triage": {str(k): v for k, v in tri.items()},
                     "deep": {str(k): v for k, v in deep.items()}, "digest": digest})
    feeds.save_json(feeds.QUEUE, [])
    print("Claude usage:\n" + llm.usage_summary())

    if not args.no_whatsapp:
        whatsapp.send_digest(cfg, date_label, digest.get("whatsapp_highlights", ""), url)


if __name__ == "__main__":
    sys.exit(main())
