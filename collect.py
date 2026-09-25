#!/usr/bin/env python3
"""Collects new SAP Community items into the queue. Runs every 3 hours, no AI cost."""
from pathlib import Path

import yaml

from sapdigest import feeds

if __name__ == "__main__":
    cfg = yaml.safe_load((Path(__file__).resolve().parent / "config.yaml").read_text(encoding="utf-8"))
    added, failures = feeds.collect(cfg)
    if failures and len(failures) == len(cfg["feeds"]):
        raise SystemExit("Every feed failed:\n" + "\n".join(failures))
