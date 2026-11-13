"""Plain-English summarization of a zoning application's raw city text, via
OpenRouter. Shared by the live on-demand path (pipeline.py, called when a
user actually looks up an address near an application with no cached
summary) and the optional offline pre-warm script
(scripts/build_zoning_summaries.py).

Defaults to a free (":free"-suffixed) OpenRouter model, so cost is $0 by
default — no credits, no credit limit, no OPENROUTER_API_KEY spend cap
tuning needed at all. The one wrinkle: as of 2026-09, most current free
models default to emitting a chain-of-thought "reasoning" trace before the
final answer, which both costs latency and can exhaust max_tokens before
ever producing content (see REASONING below — several free models tried
during development did exactly this). google/nvidia's nemotron-3.5-lightning
is the one that let reasoning be disabled outright and gave clean, on-topic
one-liners in testing; other free models are worth trying but check they
don't 400 with "Reasoning is mandatory for this endpoint" first.
Free-tier models also share a request pool across all OpenRouter users, so
expect occasional 429s under load (handled as a soft failure — see
pipeline.py's broad except, which falls back to the raw description).

If you'd rather pay for a faster/higher-quality paid model instead, set
OPENROUTER_MODEL (e.g. "google/gemini-2.5-flash-lite", ~$0.10/1M input
tokens) and cap spend with a credit limit on the API key itself, in
OpenRouter's dashboard — that's the only place cost is actually capped,
regardless of whether a call happens live from the running app or from the
batch script.
"""
from __future__ import annotations

import os

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3.5-lightning:free")
# Disabling reasoning is required for the default free model above to return
# a direct answer instead of burning max_tokens on a "thinking" trace (see
# module docstring). Some other reasoning models reject this outright with
# "Reasoning is mandatory for this endpoint" — if you switch OPENROUTER_MODEL
# to one of those, drop this from the request payload and raise max_tokens
# instead to leave room for both the reasoning trace and the final answer.
REASONING_PARAM = {"enabled": False}

SUMMARY_PROMPT = (
    "You are summarizing a City of Toronto zoning/development application for a resident "
    "checking what's happening near their address. Write ONE plain-English sentence (under "
    "35 words) covering what's being proposed and its scale (storeys/units if mentioned). "
    "No legalese, no restating the application type. If the text gives no useful detail, "
    "reply exactly: NO_SUMMARY.\n\nApplication text:\n{description}"
)


class SpendCapReached(Exception):
    """Raised when OpenRouter returns 402 — the API key's credit limit has been hit."""


def summarize(description: str, api_key: str, timeout: int = 15) -> str | None:
    """Call OpenRouter for one plain-English summary. Returns None if the
    model reports nothing worth summarizing (or returns no usable content at
    all — e.g. a reasoning model that ran out of tokens mid-thought).
    Raises SpendCapReached on a 402."""
    resp = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": OPENROUTER_MODEL,
            "messages": [{"role": "user", "content": SUMMARY_PROMPT.format(description=description[:2000])}],
            "max_tokens": 200,
            "temperature": 0.3,
            "reasoning": REASONING_PARAM,
        },
        timeout=timeout,
    )
    if resp.status_code == 402:
        raise SpendCapReached()
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"].get("content")
    if not text:
        return None
    text = text.strip()
    return None if text == "NO_SUMMARY" else text


if __name__ == "__main__":
    import sys

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        sys.exit("Set OPENROUTER_API_KEY to test this module directly.")

    sample = (
        "Proposed redevelopment of the lands with a 36-storey Private Student Residence "
        "(112.58 metres height, including the mechanical penthouse) with 426 dwelling units."
    )
    print(summarize(sample, api_key))
