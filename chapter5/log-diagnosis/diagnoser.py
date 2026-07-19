"""
diagnoser.py —— Diagnostic Agent (actual OpenAI calls)

Two phases, both real LLM calls:
  1) diagnose()        Read trajectory set + architecture + PRD -> structured problem report (priority/module/description/suggestion)
  2) gen_test_cases()  Based on problem report -> generate regression test cases executable by replay.py

Default model gpt-5.6-luna, output uses JSON mode for stable parsing.
"""

import json
import os
from typing import Dict, Any, List

from openai import OpenAI

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

# --- Generic OpenRouter fallback ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _map_to_openrouter_model(model: str) -> str:
    """Map direct model names to OpenRouter IDs (non-mappable IDs fall back to current cheap flagship)."""
    if not model or "/" in model:
        return model or "openai/gpt-5.6-luna"
    m = model.lower()
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai/" + model
    if m.startswith("claude"):
        if "haiku" in m:
            return "anthropic/claude-haiku-4.5"
        if "sonnet" in m:
            return "anthropic/claude-sonnet-4.6"
        return "anthropic/claude-opus-4.8"
    if m.startswith("gemini"):
        return "google/" + model
    return "openai/gpt-5.6-luna"

# Assertion DSL description for LLM test case generation (must be consistent with replay.py)
_ASSERTION_SPEC = """Available assertion types (assertion.type can only be one of the following):
- "step_present"    params: {"tool": <tool name>}                 The tool must appear in the trajectory
- "tool_succeeds"   params: {"tool": <tool name>}                 The tool must eventually succeed without "false success after multiple failures"
- "latency_under"   params: {"tool": <tool name>, "threshold_ms": <integer>}  The tool's single latency must be below the threshold
- "final_status_is" params: {"value": "success"|"failed"}        The final task status must equal the given value"""


class Diagnoser:
    def __init__(self, model: str = MODEL):
        # Generic OpenRouter fallback: no direct key, or default gpt-5.x (direct requires org real-name auth) switches to OpenRouter.
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        orkey = os.getenv("OPENROUTER_API_KEY")
        prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
        if prefer_or or (not api_key and orkey):
            api_key, base_url, model = orkey, OPENROUTER_BASE_URL, _map_to_openrouter_model(model)
        # timeout / max_retries: let occasional network/SSL jitter auto-retry without crashing the whole round
        kw = {"timeout": 60.0, "max_retries": 3}
        if api_key:
            kw["api_key"] = api_key
        if base_url:
            kw["base_url"] = base_url
        self.client = OpenAI(**kw)
        self.model = model
        # Inference models (gpt-5 / o series etc.) do not accept temperature=0.
        self._temp = (1 if any(k in (model or "").lower()
                               for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
                      else 0)

    # ---------- Phase 1: Diagnosis ----------
    def diagnose(self, architecture: str, prd: str,
                 trajectories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        traj_text = json.dumps(trajectories, ensure_ascii=False, indent=2)
        system = (
            "You are a senior Agent system diagnostic expert. Given system architecture docs, PRD, and a set of production trajectories,"
            "you need to determine whether each trajectory's execution flow meets the architecture and PRD requirements, identify problem patterns, locate specific modules,"
            "and output a structured problem report. Only report issues with evidence; do not fabricate."
        )
        user = f"""# System Architecture
{architecture}

# PRD
{prd}

# Production Trajectory Set (JSON)
{traj_text}

# Task
Check each trajectory against the PRD/architecture one by one, find deviations. Output as JSON with structure:
{{
  "problems": [
    {{
      "title": "One-line problem title",
      "priority": "P0|P1|P2|P3",
      "module": "Involved module name (from architecture)",
      "description": "Problem description, citing specific trajectory and turns as evidence",
      "suggestion": "Actionable improvement suggestion",
      "trajectory_ids": ["Involved trajectory IDs"],
      "focus_turns": [Indexes of key interaction turns],
      "prd_ref": "Corresponding PRD entry (e.g., R1/R2/R3)",
      "suggested_assignee": "Suggested assignee (can be left blank)"
    }}
  ]
}}Output only JSON."""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=self._temp,
        )
        data = json.loads(resp.choices[0].message.content)
        return data.get("problems", [])

    # ---------- Phase 2: Generate Regression Test Cases ----------
    def gen_test_cases(self, problems: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        prob_text = json.dumps(problems, ensure_ascii=False, indent=2)
        system = (
            "You are a test engineer. Based on the diagnosed issues, generate one regression test case per issue,"
            "the test case references the problem trajectory ID and key interaction turns, and provides an assertion evaluable by the automated replay framework."
        )
        user = f"""# Diagnosed Issues
{prob_text}

# Assertion DSL
{_ASSERTION_SPEC}

# Task
Generate 1 regression test case per issue. The assertion should express "the correct behavior the system should satisfy after fixing"
(e.g., verify_refund_eligibility should appear before refund; process_refund should eventually succeed; check_stock latency should be < 5000ms).
Output as JSON:
{{
  "test_cases": [
    {{
      "test_id": "RT-001",
      "trajectory_id": "Referenced problem trajectory ID",
      "focus_turn": Key turn index,
      "description": "What this test case verifies",
      "assertion": {{"type": "...", "params": {{...}}}}
    }}
  ]
}}Output only JSON."""
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=self._temp,
        )
        data = json.loads(resp.choices[0].message.content)
        return data.get("test_cases", [])
