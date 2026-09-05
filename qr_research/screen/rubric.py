"""Rubric screener: rules stage (deterministic) + LLM stage (rubric_prompt_v1.md).

The LLM stage needs SCREENER_API_KEY and SCREENER_PROVIDER=anthropic. Without a key it
runs in dry mode: rules only, and candidates keep whatever screen_result their
generator assigned (the FDIC drafts are tagged in code, reviewed by hand for Phase 0).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests

from qr_research.connectors.base import COUNTIES

ROOT = Path(__file__).resolve().parents[2]
PROMPT = (ROOT / "rubric_prompt_v1.md").read_text()
FEWSHOT = (ROOT / "reference" / "published_observations.md").read_text()
VALID_COUNTIES = set(COUNTIES.values())


def rules_stage(c: dict) -> tuple[bool, str]:
    if not set(c.get("counties", [])) & VALID_COUNTIES:
        return False, "outside the five counties"
    if c.get("candidate_type") == "individual":
        return False, "individual-level record"
    if not c.get("evidence_urls"):
        return False, "no primary-record URL"
    if c.get("feed") == "lens" and not c.get("recipe_ids"):
        return False, "lens candidate without a recipe (fabrication guard)"
    return True, ""


def llm_stage(c: dict) -> dict:
    key, provider = os.environ.get("SCREENER_API_KEY"), os.environ.get("SCREENER_PROVIDER", "anthropic")
    if not key:
        return {}
    if provider != "anthropic":
        raise NotImplementedError(f"provider {provider} not wired; see DECISIONS.md")
    body = {
        "model": os.environ.get("SCREENER_MODEL", "claude-sonnet-4-6"), "max_tokens": 800,
        "system": PROMPT + "\n\n# Few-shot examples\n" + FEWSHOT,
        "messages": [{"role": "user", "content": json.dumps({k: v for k, v in c.items() if k not in ("axis_a", "axis_b", "function", "screen_result")})}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=body, timeout=90)
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json()["content"])
    return json.loads(text.strip().strip("`").removeprefix("json").strip())


def screen(c: dict) -> dict:
    ok, reason = rules_stage(c)
    if not ok:
        return {**c, "screen_result": "kill", "why_hold": reason}
    out = llm_stage(c)
    if not out:
        return c  # dry mode: keep generator's tags
    return {**c, **{k: out[k] for k in ("screen_result", "axis_a", "axis_b", "function", "stock_or_flow", "why_it_might_matter", "coverage_note") if k in out},
            "why_hold": out.get("kill_or_hold_reason", "")}


if __name__ == "__main__":
    import sys
    cands = json.load(open(sys.argv[1]))
    res = [screen(c) for c in cands]
    json.dump(res, open(sys.argv[1], "w"), indent=1)
    for c in res:
        print(c["screen_result"], "|", c["headline"])
