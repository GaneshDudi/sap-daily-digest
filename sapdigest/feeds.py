"""Collects new items from the configured feeds into data/queue.json.

Runs every few hours (no AI cost) so nothing is missed even on busy days,
because each RSS feed only shows its latest N items.
"""
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
QUEUE = DATA / "queue.json"
SEEN = DATA / "seen.json"
UA = "Mozilla/5.0 (compatible; SAPDailyDigest/1.0; personal feed reader)"
SEEN_RETENTION_DAYS = 30
MAX_ITEM_AGE_DAYS = 2  # ignore anything older (mainly matters on the first run)


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def clean_html(raw, limit=12000):
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style", "img"]):
        tag.decompose()
    for block in soup.find_all(["pre", "p", "li", "h1", "h2", "h3", "h4", "br", "tr"]):
        block.insert_before("\n")
    text = soup.get_text(" ")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()[:limit]


def _entry_time(entry):
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if t:
        return dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
    return dt.datetime.now(dt.timezone.utc)


def _entry_body(entry):
    if entry.get("content"):
        return entry["content"][0].get("value", "")
    return entry.get("summary", "") or entry.get("description", "")


def parse_feed(raw_bytes, feed_cfg):
    parsed = feedparser.parse(raw_bytes)
    items = []
    for e in parsed.entries:
        link = e.get("link", "")
        uid = e.get("id") or link or e.get("title", "")
        if not uid:
            continue
        items.append({
            "key": hashlib.sha1(uid.encode("utf-8")).hexdigest()[:16],
            "title": clean_html(e.get("title", "(untitled)"), 300),
            "link": link,
            "published": _entry_time(e).isoformat(),
            "author": e.get("author", ""),
            "tags": [t.get("term", "") for t in e.get("tags", []) if t.get("term")][:12],
            "feed": feed_cfg["name"],
            "kind": feed_cfg.get("kind", "other"),
            "text": clean_html(_entry_body(e)),
        })
    return items


def fetch_feed(feed_cfg):
    r = requests.get(feed_cfg["url"], headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()
    return parse_feed(r.content, feed_cfg)


def fetch_full_text(url):
    """Used when a feed only gave a short excerpt."""
    try:
        import trafilatura
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25)
        if r.ok:
            return (trafilatura.extract(r.text, include_tables=True) or "")[:12000]
    except Exception as exc:  # network or parsing problem: fall back to the excerpt
        print(f"  full-text fetch failed for {url}: {exc}")
    return ""


def collect(config):
    queue = load_json(QUEUE, [])
    seen = load_json(SEEN, {})
    now = dt.datetime.now(dt.timezone.utc)
    added, failures = 0, []

    for feed_cfg in config["feeds"]:
        try:
            items = fetch_feed(feed_cfg)
        except Exception as exc:
            failures.append(f"{feed_cfg['name']}: {exc}")
            print(f"Feed failed: {feed_cfg['name']}: {exc}")
            continue
        too_old = now - dt.timedelta(days=MAX_ITEM_AGE_DAYS)
        new = [it for it in items
               if it["key"] not in seen and dt.datetime.fromisoformat(it["published"]) > too_old]
        for it in new:
            seen[it["key"]] = now.isoformat()
            queue.append(it)
        added += len(new)
        print(f"{feed_cfg['name']}: {len(items)} in feed, {len(new)} new")

    cutoff = now - dt.timedelta(days=SEEN_RETENTION_DAYS)
    seen = {k: v for k, v in seen.items() if dt.datetime.fromisoformat(v) > cutoff}

    save_json(QUEUE, queue)
    save_json(SEEN, seen)
    print(f"Queued {added} new items. Queue size now {len(queue)}.")
    return added, failures
