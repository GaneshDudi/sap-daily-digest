"""Sends the daily digest through Meta's official WhatsApp Cloud API.

Business-initiated messages must use a Meta-approved template, so the
digest arrives as the `sap_daily_digest` template with three values:
the date, a one-line highlights summary, and the full report link.
"""
import os
import re

import requests

TEMPLATE_PARAM_LIMIT = 700  # keeps the whole message under WhatsApp's 1024-char body limit


def _env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing secret {name}. Add it under GitHub > Settings > Secrets > Actions.")
    return value


def _clean_param(text, limit=TEMPLATE_PARAM_LIMIT):
    # Template parameters may not contain newlines, tabs or 4+ consecutive spaces.
    text = re.sub(r"[\r\n\t]+", " ", text or "")
    text = re.sub(r" {2,}", " ", text).strip()
    if len(text) > limit:
        text = text[: limit - 1].rsplit(" ", 1)[0] + "…"
    return text or "-"


def _post(cfg, payload):
    url = (f"https://graph.facebook.com/{cfg['whatsapp']['graph_api_version']}/"
           f"{_env('WA_PHONE_NUMBER_ID')}/messages")
    r = requests.post(url, json=payload, timeout=30,
                      headers={"Authorization": f"Bearer {_env('WA_TOKEN')}"})
    if not r.ok:
        raise RuntimeError(f"WhatsApp API error {r.status_code}: {r.text}")
    return r.json()


def send_digest(cfg, date_label, highlights, report_url):
    wa = cfg["whatsapp"]
    payload = {
        "messaging_product": "whatsapp",
        "to": _env("WA_TO").lstrip("+"),
        "type": "template",
        "template": {
            "name": wa["template_name"],
            "language": {"code": wa["template_language"]},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": _clean_param(date_label, 60)},
                    {"type": "text", "text": _clean_param(highlights)},
                    {"type": "text", "text": _clean_param(report_url, 200)},
                ],
            }],
        },
    }
    result = _post(cfg, payload)
    print(f"WhatsApp digest accepted by Meta: {result.get('messages', [{}])[0].get('id', '?')}")
    return result


def send_hello_world(cfg):
    """Setup check: Meta's pre-approved test template."""
    payload = {
        "messaging_product": "whatsapp",
        "to": _env("WA_TO").lstrip("+"),
        "type": "template",
        "template": {"name": "hello_world", "language": {"code": "en_US"}},
    }
    result = _post(cfg, payload)
    print(f"hello_world accepted by Meta: {result}")
    return result
