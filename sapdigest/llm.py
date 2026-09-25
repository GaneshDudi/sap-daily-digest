"""Thin wrapper around the Claude API that always returns structured JSON.

Forcing a tool call makes Claude reply in the exact schema we define,
so the pipeline never has to guess at free-text formats.
"""
import threading
from collections import defaultdict

import anthropic

_client = None
_lock = threading.Lock()
usage = defaultdict(lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0})


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=6, timeout=300)
    return _client


def call_tool(model, system, user, tool_name, schema, max_tokens=4000):
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        tools=[{
            "name": tool_name,
            "description": "Record the structured result of your analysis.",
            "input_schema": schema,
        }],
        tool_choice={"type": "tool", "name": tool_name},
        messages=[{"role": "user", "content": user}],
    )
    with _lock:
        u = usage[model]
        u["calls"] += 1
        u["input_tokens"] += resp.usage.input_tokens
        u["output_tokens"] += resp.usage.output_tokens
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(f"{tool_name}: response cut off at max_tokens={max_tokens}")
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError(f"{tool_name}: no structured output returned")


def usage_summary():
    lines = []
    for model, u in usage.items():
        lines.append(f"{model}: {u['calls']} calls, "
                     f"{u['input_tokens']:,} input / {u['output_tokens']:,} output tokens")
    return "\n".join(lines) or "No API calls made."
