#!/usr/bin/env python3
"""Daily SAP job market agent.

1. Collect   jobs from Adzuna, your job-alert emails and company careers sites.
2. Extract   jobs from alert emails (Claude reads each email).
3. De-dupe   the same job from several sources appears once; jobs already reported are skipped.
4. Analyse   every new job: SAP-technical or not, role, seniority, skills, match with your profile.
5. Trends    daily skill counts are stored, so the report compares this week with last week.
6. Report    Claude writes the market summary; the page is published under docs/jobs/.

Runs on your Claude subscription through Claude Code, like the SAP Community digest.
"""
import datetime as dt
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from sapdigest import feeds, job_report, job_sources, llm

ROOT = Path(__file__).resolve().parent
JOBDATA = ROOT / "data" / "jobs"
SEEN = JOBDATA / "seen.json"
HISTORY = JOBDATA / "skill_history.json"
SEEN_DAYS = 45

SKILLS = [
    "ABAP OO", "Modern ABAP syntax", "RAP", "CDS views", "AMDP", "OData / Gateway", "Fiori / UI5",
    "BTP", "ABAP Cloud / Clean Core", "CAP", "S/4HANA", "ECC", "S/4HANA migration / conversion",
    "HANA / SQL performance", "BAPI / BAdI / enhancements", "IDoc / ALE / EDI", "PI/PO / CPI / Integration Suite",
    "Workflow", "Smartforms / Adobe Forms", "Reports / ALV", "Data migration (LSMW / LTMC)", "SuccessFactors",
    "Functional module knowledge", "GST / Indian localization", "AI / Joule",
]

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {"jobs": {"type": "array", "items": {"type": "object", "properties": {
        "title": {"type": "string"}, "company": {"type": "string"}, "location": {"type": "string"},
        "experience": {"type": "string", "description": "As written in the email, empty if not given"},
        "url": {"type": "string", "description": "The job's link exactly as it appears in the email"},
        "snippet": {"type": "string", "description": "Any skills or description text given for this job"}},
        "required": ["title", "company", "location", "experience", "url", "snippet"]}}},
    "required": ["jobs"],
}

ANALYSE_SCHEMA = {
    "type": "object",
    "properties": {"jobs": {"type": "array", "items": {"type": "object", "properties": {
        "i": {"type": "integer"},
        "sap_technical": {"type": "boolean",
                          "description": "True if the role involves SAP ABAP or SAP technical development"},
        "role": {"type": "string", "enum": ["ABAP Developer", "Senior / Lead Developer", "Technical Architect",
                                            "Techno-functional", "Trainer / Corporate trainer",
                                            "Functional consultant", "Other SAP", "Not SAP"]},
        "experience": {"type": "string", "description": "Years required, e.g. '5-8 years', or 'Not stated'"},
        "work_mode": {"type": "string", "enum": ["Onsite", "Hybrid", "Remote", "Not stated"]},
        "skills": {"type": "array", "items": {"type": "string", "enum": SKILLS}},
        "match": {"type": "integer", "minimum": 1, "maximum": 5,
                  "description": "How well the job fits the candidate profile, 5 = excellent"},
        "match_reason": {"type": "string", "description": "One short sentence"}},
        "required": ["i", "sap_technical", "role", "experience", "work_mode", "skills", "match", "match_reason"]}}},
    "required": ["jobs"],
}

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "One sentence on today's SAP job market, max 25 words"},
        "market_summary": {"type": "string", "description": "2 short paragraphs"},
        "skill_insights": {"type": "array", "maxItems": 5, "items": {"type": "string"},
                           "description": "What the skill numbers and trends mean, one sentence each"},
        "teaching_insights": {"type": "array", "maxItems": 4, "items": {"type": "string"},
                              "description": "What a trainer should teach or emphasise, based on demand"},
        "advice": {"type": "string", "description": "2-3 sentences of practical advice for the candidate"},
    },
    "required": ["headline", "market_summary", "skill_insights", "teaching_insights", "advice"],
}


def load_config():
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def extract_from_emails(emails, cfg):
    system = ("You read job alert emails from Indian job portals. List every individual job in the email "
              "exactly as given. Do not invent jobs, companies or links. Skip ads, tips and non-job content.")

    def run(em):
        try:
            out = llm.call_tool(cfg["models"]["fast"], system,
                                f"From: {em['sender']}\nSubject: {em['subject']}\n\n{em['text']}",
                                "record_jobs", EXTRACT_SCHEMA)
            return [job_sources._job(f"Email: {em['sender']}", j["title"], j["company"], j["location"],
                                     (f"Experience: {j['experience']}. " if j["experience"] else "") + j["snippet"],
                                     j["url"]) for j in out.get("jobs", [])]
        except Exception as exc:
            print(f"Email extraction failed ({em['subject'][:60]}): {exc}")
            return []

    jobs = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows in pool.map(run, emails):
            jobs += rows
    return jobs


def analyse(jobs, cfg):
    jc = cfg["jobs"]
    system = ("You analyse job postings for this candidate:\n" + jc["profile"] +
              "\nFor each job decide whether it is an SAP technical (ABAP / SAP development) role, classify it, "
              "extract required experience and skills (only from the given skill list, only if the posting "
              "mentions or clearly implies them), and score the match with the candidate. Judge only from the "
              "text given; if details are missing, say 'Not stated'.")
    size = jc.get("analysis_batch_size", 40)
    batches = [list(range(s, min(s + size, len(jobs)))) for s in range(0, len(jobs), size)]

    def run(batch):
        lines = "\n".join(f"[{i}] {jobs[i]['title']} | {jobs[i]['company']} | {jobs[i]['location']} | "
                          f"{jobs[i]['snippet'][:600]}" for i in batch)
        try:
            return llm.call_tool(cfg["models"]["fast"], system, f"Analyse these {len(batch)} jobs:\n{lines}",
                                 "record_analysis", ANALYSE_SCHEMA).get("jobs", [])
        except Exception as exc:
            print(f"Analysis batch failed: {exc}")
            return []

    with ThreadPoolExecutor(max_workers=2) as pool:
        for rows in pool.map(run, batches):
            for r in rows:
                i = r.pop("i", None)
                if isinstance(i, int) and 0 <= i < len(jobs):
                    jobs[i].update(r)
    return jobs


def skill_trends(history, today):
    d = dt.date.fromisoformat(today)
    this_week, last_week = Counter(), Counter()
    days_with_data = 0
    for day, counts in history.items():
        age = (d - dt.date.fromisoformat(day)).days
        if 0 <= age < 7:
            this_week.update(counts)
            days_with_data += 1
        elif 7 <= age < 14:
            last_week.update(counts)
    rows = [{"skill": s, "this_week": this_week[s], "last_week": last_week[s]} for s in SKILLS
            if this_week[s] or last_week[s]]
    rows.sort(key=lambda r: -r["this_week"])
    return rows, days_with_data


def main():
    cfg = load_config()
    jc = cfg["jobs"]
    now = dt.datetime.now(ZoneInfo(cfg["timezone"]))
    date_iso, date_label = now.strftime("%Y-%m-%d"), now.strftime("%A, %-d %B %Y")

    # 1. Collect
    collected, coverage = [], {}
    try:
        found = job_sources.adzuna(jc)
        collected += found
        coverage["Adzuna (India job index)"] = f"{len(found)} jobs"
    except Exception as exc:
        coverage["Adzuna (India job index)"] = f"failed: {str(exc)[:120]}"
    try:
        emails = job_sources.alert_emails(jc)
        coverage["Job alert emails"] = f"{len(emails)} emails"
        from_email = extract_from_emails(emails, cfg)
        coverage["Job alert emails"] += f", {len(from_email)} jobs"
        collected += from_email
    except Exception as exc:
        coverage["Job alert emails"] = f"failed: {str(exc)[:120]}"
    found, status = job_sources.careers(jc)
    collected += found
    coverage.update(status)
    print("Coverage:", coverage)

    # 2. De-duplicate within today and against earlier reports
    seen = feeds.load_json(SEEN, {})
    unique = {}
    for j in collected:
        if j["key"] in seen:
            continue
        if j["key"] in unique:
            if j["source"] not in unique[j["key"]]["source"]:
                unique[j["key"]]["source"] += f", {j['source']}"
            continue
        unique[j["key"]] = j
    jobs = list(unique.values())[: jc.get("max_jobs_analysed", 150)]
    print(f"Collected {len(collected)}, new and unique {len(jobs)}")

    # 3. Analyse
    if jobs:
        analyse(jobs, cfg)
    sap_jobs = [j for j in jobs if j.get("sap_technical")]

    # 4. Skill history and trends
    history = feeds.load_json(HISTORY, {})
    history[date_iso] = dict(Counter(s for j in sap_jobs for s in j.get("skills", [])))
    history = {d: c for d, c in history.items()
               if (dt.date.fromisoformat(date_iso) - dt.date.fromisoformat(d)).days < 60}
    trends, days = skill_trends(history, date_iso)
    companies = Counter(j["company"] for j in sap_jobs if j["company"]).most_common(12)

    # 5. Summary
    summary = None
    if sap_jobs:
        compact = [{"title": j["title"], "company": j["company"], "location": j["location"],
                    "role": j.get("role"), "experience": j.get("experience"), "skills": j.get("skills"),
                    "match": j.get("match")} for j in sap_jobs]
        try:
            summary = llm.call_tool(
                cfg["models"]["deep"],
                "You are an SAP talent-market analyst writing a daily briefing for this reader:\n" + jc["profile"] +
                "\nThe reader is also a trainer for experienced ABAP developers. Plain, direct English. "
                "Base every statement on the data given; with only a few days of history, say trends are early.",
                f"Date: {date_label}\nNew SAP technical jobs today: {len(sap_jobs)}\n"
                f"Jobs: {compact}\nTop companies: {companies}\n"
                f"Skill counts, this week vs last week ({days} days of data): {trends}",
                "publish_job_briefing", SUMMARY_SCHEMA)
        except Exception as exc:
            print(f"Summary failed: {exc}")

    # 6. Report and state
    job_report.render(date_iso, date_label, sap_jobs, jobs, coverage, trends, days, companies, summary,
                      now.strftime("%-d %b %Y, %H:%M %Z"))
    for j in jobs:
        seen[j["key"]] = date_iso
    seen = {k: v for k, v in seen.items()
            if (dt.date.fromisoformat(date_iso) - dt.date.fromisoformat(v)).days < SEEN_DAYS}
    feeds.save_json(SEEN, seen)
    feeds.save_json(HISTORY, history)
    feeds.save_json(JOBDATA / "archive" / f"{date_iso}.json", {"jobs": jobs, "coverage": coverage,
                                                               "summary": summary})
    print(f"SAP technical jobs: {len(sap_jobs)}")
    print("Claude usage:\n" + llm.usage_summary())


if __name__ == "__main__":
    sys.exit(main())
