"""Collects SAP job postings from several sources.

Every source returns a list of dicts with the same shape (see _job). A source that
fails never stops the run; the failure is reported in the job report instead.
"""
import datetime as dt
import email
import email.utils
import hashlib
import html
import imaplib
import os
import re
from email.header import decode_header, make_header

import feedparser
import requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (compatible; SAPJobAgent/1.0; personal job search)"


def _clean(text, limit=2000):
    text = BeautifulSoup(html.unescape(text or ""), "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def job_key(title, company):
    norm = re.sub(r"[^a-z0-9]+", " ", f"{title} | {company}".lower()).strip()
    return hashlib.sha1(norm.encode()).hexdigest()[:16]


def _job(source, title, company, location="", snippet="", url="", posted="", salary=""):
    title, company = _clean(title, 200), _clean(company, 120)
    return {"key": job_key(title, company), "source": source, "title": title, "company": company,
            "location": _clean(location, 120), "snippet": _clean(snippet, 1500), "url": url or "",
            "posted": posted or "", "salary": salary or ""}


# ── Adzuna (official job search API, India index) ─────────────────────────
def adzuna(cfg):
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY secrets are not set")
    jobs = []
    for what in cfg["adzuna_searches"]:
        r = requests.get("https://api.adzuna.com/v1/api/jobs/in/search/1", timeout=30, params={
            "app_id": app_id, "app_key": app_key, "what": what, "results_per_page": 50,
            "max_days_old": cfg.get("max_days_old", 2), "sort_by": "date",
            "content-type": "application/json"})
        r.raise_for_status()
        for x in r.json().get("results", []):
            sal = ""
            if x.get("salary_min") and str(x.get("salary_is_predicted")) != "1":
                lo, hi = int(x["salary_min"]), int(x.get("salary_max") or x["salary_min"])
                sal = f"₹{lo:,}" + (f" – ₹{hi:,}" if hi != lo else "") + " per year"
            jobs.append(_job("Adzuna", x.get("title"), (x.get("company") or {}).get("display_name", ""),
                             (x.get("location") or {}).get("display_name", ""), x.get("description"),
                             x.get("redirect_url"), (x.get("created") or "")[:10], sal))
    return jobs


# ── Job alert emails (Gmail over IMAP, read-only) ────────────────────────
def _email_text(msg):
    """Plain text of an email with links kept as 'label (url)' so Claude can extract them."""
    html_part, text_part = None, None
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "text/html" and html_part is None:
            html_part = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
        elif ctype == "text/plain" and text_part is None:
            text_part = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    if html_part:
        soup = BeautifulSoup(html_part, "html.parser")
        for tag in soup(["style", "script", "img"]):
            tag.decompose()
        for a in soup.find_all("a", href=True):
            label = a.get_text(" ", strip=True)
            if label and len(label) > 3:
                a.replace_with(f"{label} ({a['href']})")
        text = soup.get_text("\n")
    else:
        text = text_part or ""
    text = re.sub(r"[ \t\xa0]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text).strip()


def alert_emails(cfg, hours=30):
    """Returns raw alert emails; Claude turns them into job records later."""
    user, pwd = os.environ.get("GMAIL_ADDRESS"), os.environ.get("GMAIL_APP_PASSWORD")
    if not (user and pwd):
        raise RuntimeError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD secrets are not set")
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).strftime("%d-%b-%Y")
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)
    out = []
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        imap.login(user, pwd.replace(" ", ""))
        imap.select("INBOX", readonly=True)
        for sender in cfg["email_senders"]:
            status, data = imap.search(None, f'(SINCE "{since}" FROM "{sender}")')
            if status != "OK":
                continue
            for num in data[0].split()[-15:]:  # newest 15 per sender is plenty
                status, parts = imap.fetch(num, "(RFC822)")
                if status != "OK" or not parts or not isinstance(parts[0], tuple):
                    continue
                msg = email.message_from_bytes(parts[0][1])
                try:
                    when = email.utils.parsedate_to_datetime(msg.get("Date"))
                    if when and when.tzinfo and when < cutoff:
                        continue
                except (TypeError, ValueError):
                    pass
                out.append({"sender": sender, "subject": str(make_header(decode_header(msg.get("Subject", "")))),
                            "text": _email_text(msg)[:15000]})
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return out


# ── Company careers sites ────────────────────────────────────────────────
def successfactors(site):
    jobs = []
    for kw in site.get("keywords", ["abap"]):
        url = f"{site['base_url'].rstrip('/')}/services/rss/job/"
        r = requests.get(url, params={"locale": "en_US", "keywords": f"({kw})"},
                         headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
        for e in feed.entries:
            t = e.get("published_parsed")
            posted = dt.date(*t[:3]).isoformat() if t else ""
            jobs.append(_job(f"{site['name']} careers", e.get("title"), site["name"],
                             e.get("location", "") or "", e.get("summary", ""), e.get("link"), posted))
    return jobs


def workday(site):
    jobs = []
    api = f"https://{site['host']}/wday/cxs/{site['tenant']}/{site['site']}/jobs"
    for kw in site.get("keywords", ["SAP ABAP"]):
        r = requests.post(api, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": kw},
                          headers={"User-Agent": UA, "Accept": "application/json"}, timeout=30)
        r.raise_for_status()
        for p in r.json().get("jobPostings", []):
            link = f"https://{site['host']}/{site['site']}{p.get('externalPath', '')}"
            jobs.append(_job(f"{site['name']} careers", p.get("title"), site["name"],
                             p.get("locationsText", ""), "", link, p.get("postedOn", "")))
    return jobs


CAREER_TYPES = {"successfactors": successfactors, "workday": workday}


def careers(cfg):
    """Returns (jobs, per-site status)."""
    jobs, status = [], {}
    for site in cfg.get("careers", []):
        try:
            found = CAREER_TYPES[site["type"]](site)
            jobs += found
            status[f"{site['name']} careers"] = f"{len(found)} jobs"
        except Exception as exc:
            status[f"{site['name']} careers"] = f"failed: {str(exc)[:120]}"
    return jobs, status
