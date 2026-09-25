"""Runs Claude through Claude Code in headless mode, using your Claude subscription.

Each call starts `claude -p` with:
  * your subscription token (CLAUDE_CODE_OAUTH_TOKEN), so there is no API bill
  * a custom system prompt and no tools, so Claude only reads and answers
  * a JSON schema, so the answer comes back in exactly the structure we need
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
from collections import defaultdict

WORKDIR = tempfile.mkdtemp(prefix="sapdigest-")
LIMIT_WORDS = re.compile(r"usage limit|limit reached|out of (extra )?usage|weekly limit|session limit", re.I)

usage = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
_lock = threading.Lock()
_limit_hit = threading.Event()


class UsageLimitReached(RuntimeError):
    """Your Claude plan's usage limit was reached; remaining calls are skipped."""


def limit_reached():
    return _limit_hit.is_set()


def _claude_bin():
    path = shutil.which("claude")
    if not path:
        raise RuntimeError("Claude Code is not installed on this machine (the 'claude' command was not found).")
    return path


def _parse_output(stdout):
    stdout = (stdout or "").strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {"result": stdout}


def call_tool(model, system, user, tool_name, schema, timeout=900):
    """Ask Claude one question and return a dict matching `schema`."""
    if _limit_hit.is_set():
        raise UsageLimitReached("Skipped because the Claude usage limit was reached earlier in this run.")

    sys_file = os.path.join(WORKDIR, f"{tool_name}-{threading.get_ident()}.txt")
    with open(sys_file, "w", encoding="utf-8") as f:
        f.write(system + "\n\nReply only through the structured output format you have been given.")

    cmd = [_claude_bin(), "-p",
           "--model", model,
           "--output-format", "json",
           "--json-schema", json.dumps(schema),
           "--system-prompt-file", sys_file,
           "--tools", "",
           "--no-session-persistence",
           "--max-turns", "4"]
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # make sure the subscription token is what gets used

    proc = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout, cwd=WORKDIR, env=env)
    data = _parse_output(proc.stdout)

    with _lock:
        u = usage[model]
        u["calls"] += 1
        tok = data.get("usage") or {}
        u["input_tokens"] += (tok.get("input_tokens") or 0) + (tok.get("cache_read_input_tokens") or 0) \
            + (tok.get("cache_creation_input_tokens") or 0)
        u["output_tokens"] += tok.get("output_tokens") or 0
        u["cost_usd"] += data.get("total_cost_usd") or 0.0

    if proc.returncode != 0 or data.get("is_error"):
        detail = str(data.get("result") or proc.stderr or proc.stdout or "no output")[:600]
        if LIMIT_WORDS.search(detail):
            _limit_hit.set()
            raise UsageLimitReached(detail)
        raise RuntimeError(f"{tool_name}: Claude Code failed (exit {proc.returncode}): {detail}")

    structured = data.get("structured_output")
    if isinstance(structured, dict):
        return structured
    text = data.get("result") or ""
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    raise RuntimeError(f"{tool_name}: Claude did not return structured output. Got: {text[:300]}")


def usage_summary():
    if not usage:
        return "No Claude calls made."
    lines = []
    for model, u in usage.items():
        lines.append(f"{model}: {u['calls']} calls, {u['input_tokens']:,} input / "
                     f"{u['output_tokens']:,} output tokens "
                     f"(API-equivalent ${u['cost_usd']:.2f}; covered by your subscription, not billed)")
    if _limit_hit.is_set():
        lines.append("NOTE: your Claude usage limit was reached during this run, so some steps were skipped.")
    return "\n".join(lines)
