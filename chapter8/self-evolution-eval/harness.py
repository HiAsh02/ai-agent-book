"""
Four-layer hierarchical validation harness.

Input: a trajectory of the tested Agent (schema in agent.py), and the corresponding task definition.
Output: scores for each layer and an overall rating.

Four layers:
  L1 Task Correctness        — Check the final answer using the dataset's correctness_criteria (rules/judgment).
  L2 Tool Discovery Effectiveness    — Heuristic analysis of search keywords / visited webpages / selected libraries, judging whether the discovery is relevant and avoids pitfalls.
  L3 Tool Creation Quality      — LLM-as-a-Judge, scoring the created tool code according to a Rubric (error handling/parameter validation/documentation).
  L4 Tool Reuse Capability      — Analyze the trajectory of a "second similar task" to see if it directly retrieves a registered tool instead of repeating search and creation.
"""

import json
import re
from typing import Optional

from config import Config


# Weights of each layer in the overall rating (if a layer is N/A, renormalize proportionally among available layers)
LAYER_WEIGHTS = {"L1": 0.35, "L2": 0.25, "L3": 0.25, "L4": 0.15}

# All four layers, for CLI / upper layer selection
ALL_LAYERS = ("L1", "L2", "L3", "L4")


# ---------------------------------------------------------------------------
# L1 Task Correctness
# ---------------------------------------------------------------------------
def layer1_correctness(task: dict, trajectory: dict) -> dict:
    answer = trajectory.get("final_answer", "") or ""
    crit = task["correctness_criteria"]
    check = crit["check"]
    passed = False
    if check == "regex":
        passed = re.search(crit["pattern"], answer) is not None
    elif check == "contains_any":
        low = answer.lower()
        passed = any(v.lower() in low for v in crit["values"])
    return {
        "score": 1.0 if passed else 0.0,
        "passed": passed,
        "detail": f"Criteria[{check}] -> {'Pass' if passed else 'Fail'}；{crit['description']}",
    }


# ---------------------------------------------------------------------------
# L2 Tool Discovery Effectiveness
# ---------------------------------------------------------------------------
def _selected_libraries(trajectory: dict):
    return [s["library"] for s in trajectory["steps"] if s["action"] == "select_library"]


def _search_queries(trajectory: dict):
    return [s["query"] for s in trajectory["steps"] if s["action"] == "search"]


def layer2_discovery(task: dict, trajectory: dict) -> dict:
    steps = trajectory["steps"]
    reused = any(s["action"] == "retrieve_tool" for s in steps)
    did_discovery = any(s["action"] in ("search", "select_library", "create_tool") for s in steps)
    if reused and not did_discovery:
        # This is a reuse, no new discovery activity — this layer is not applicable
        return {"score": None, "detail": "This time directly reused a registered tool, no new discovery activity, L2 not applicable."}

    queries = _search_queries(trajectory)
    selected = _selected_libraries(trajectory)
    kws = [k.lower() for k in task.get("discovery_keywords", [])]
    recommended = [l.lower() for l in task["reference_solution"]["libraries"]]
    pit = task.get("known_pitfalls", {})
    bad_libs = [b.lower() for b in (pit.get("deprecated_libraries", []) + pit.get("paid_or_registration_apis", []))]

    # Heuristic indicators
    on_topic = any(any(k in q.lower() for k in kws) for q in queries) if queries else False
    visited_web = any(s["action"] == "read_web" for s in steps)

    def _match(lib, pool):
        lo = lib.lower()
        return any(p.split("(")[0].strip() in lo or lo in p for p in pool)

    selected_recommended = any(_match(l, recommended) for l in selected)
    hit_pitfall = any(_match(l, bad_libs) for l in selected)
    avoided_pitfalls = not hit_pitfall

    score = (
        0.40 * selected_recommended
        + 0.25 * on_topic
        + 0.25 * avoided_pitfalls
        + 0.10 * visited_web
    )
    return {
        "score": round(score, 3),
        "components": {
            "on_topic_search": on_topic,
            "visited_web": visited_web,
            "selected_recommended_lib": selected_recommended,
            "avoided_pitfalls": avoided_pitfalls,
        },
        "selected_libraries": selected,
        "detail": (
            f"Search relevance={on_topic} Visited webpages={visited_web} Selected recommended library={selected_recommended} "
            f"Avoided pitfalls={avoided_pitfalls}(Library selection:{selected}）"
        ),
    }


# ---------------------------------------------------------------------------
# L3 Tool Creation Quality (LLM-as-a-Judge, according to Rubric)
# ---------------------------------------------------------------------------
_JUDGE_SYSTEM = (
    "You are a strict code review expert responsible for evaluating the quality of a Python tool function automatically created by a self-evolving Agent."
    "Please score based solely on the given code, scoring 0-3 on each of the following 4 dimensions (0=not at all, 1=very weak, 2=average, 3=excellent):\n"
    "  error_handling  Error handling: whether try/except is used to handle network/IO/parsing exceptions, providing useful information.\n"
    "  input_validation Parameter validation: whether input types/values/boundaries are checked, and whether illegal inputs raise errors.\n"
    "  documentation   Documentation completeness: whether there is a clear docstring explaining purpose, parameters, returns, and exceptions.\n"
    "  robustness      Robustness and fit: whether the implementation fits the task goal, and whether edge cases and failure scenarios are considered.\n"
    "Return only JSON, in the form:"
    '{"error_handling":int,"input_validation":int,"documentation":int,"robustness":int,"comment":"brief Chinese comment"}'
)


def _parse_judge_json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


def layer3_tool_quality(task: dict, trajectory: dict, judge_model: Optional[str] = None) -> dict:
    created = trajectory.get("created_tools", [])
    if not created:
        return {"score": None, "detail": "No new tool was created in this trajectory (possibly reuse), L3 not applicable."}

    tool = created[0]
    model = Config.map_model(judge_model or Config.JUDGE_MODEL)
    client = Config.get_client()
    user = (
        f"Task goal:{task['goal']}\n\n"
        f"The tool function `{tool['name']}` created by the Agent has the following code:\n```python\n{tool['code']}\n```"
    )
    kwargs = dict(
        model=model,
        temperature=0.0,
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    try:
        resp = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
    except Exception:
        resp = client.chat.completions.create(**kwargs)  # Some models do not support json_object
    raw = resp.choices[0].message.content or ""
    rubric = _parse_judge_json(raw)
    if not rubric:
        return {"score": 0.0, "rubric": None, "judge_text": raw, "detail": "The judge output cannot be parsed as JSON."}

    dims = ["error_handling", "input_validation", "documentation", "robustness"]
    total = sum(int(rubric.get(d, 0)) for d in dims)
    score = round(total / (3 * len(dims)), 3)
    return {
        "score": score,
        "rubric": rubric,
        "judge_text": raw,
        "tool_name": tool["name"],
        "detail": (
            f"Rubric 4 dimensions total {total}/12 -> normalized {score}；"
            f"Comments:{rubric.get('comment', '')}"
        ),
    }


# ---------------------------------------------------------------------------
# L4 Tool Reuse Capability (analyze trajectory of second similar task)
# ---------------------------------------------------------------------------
def layer4_reuse(task: dict, variant_trajectory: dict) -> dict:
    if variant_trajectory is None:
        return {"score": None, "detail": "No trajectory for second similar task provided, L4 not tested."}
    steps = variant_trajectory["steps"]
    retrieved = any(
        s["action"] == "retrieve_tool" and s.get("name") == task["tool_name"] for s in steps
    )
    re_searched = any(s["action"] == "search" for s in steps)
    re_created = any(s["action"] == "create_tool" for s in steps)

    if retrieved and not re_searched and not re_created:
        score, verdict = 1.0, "Directly retrieve and reuse registered tools (no repeated search/creation)"
    elif retrieved and (re_searched or re_created):
        score, verdict = 0.5, "Tools retrieved but still repeated search/creation"
    else:
        score, verdict = 0.0, "No reuse, repeated search and tool creation"
    return {
        "score": score,
        "retrieved_from_registry": retrieved,
        "re_searched": re_searched,
        "re_created": re_created,
        "detail": verdict,
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def aggregate(layers: dict) -> dict:
    avail = {k: v["score"] for k, v in layers.items() if v.get("score") is not None}
    if not avail:
        return {"overall": None, "used_layers": []}
    wsum = sum(LAYER_WEIGHTS[k] for k in avail)
    overall = sum(LAYER_WEIGHTS[k] * s for k, s in avail.items()) / wsum
    return {"overall": round(overall, 3), "used_layers": list(avail)}


class FourLayerEvaluator:
    """Encapsulate the four layers together. variant_trajectory is used for L4.

    layers specifies which layers to actually run (default all four layers). Only L3 requires calling the LLM over the network,
    so in offline scenarios, you can pass layers=("L1","L2","L4") to skip L3—unselected layers are marked N/A and not included in the overall evaluation."""

    def __init__(self, judge_model: Optional[str] = None, layers=ALL_LAYERS):
        self.judge_model = judge_model or Config.JUDGE_MODEL
        self.layers = tuple(layers)

    def evaluate(self, task: dict, trajectory: dict, variant_trajectory: Optional[dict] = None) -> dict:
        skipped = {"score": None, "detail": "(This layer was not selected this time, marked N/A)"}
        layers = {
            "L1": layer1_correctness(task, trajectory) if "L1" in self.layers else dict(skipped),
            "L2": layer2_discovery(task, trajectory) if "L2" in self.layers else dict(skipped),
            "L3": (
                layer3_tool_quality(task, trajectory, self.judge_model)
                if "L3" in self.layers else dict(skipped)
            ),
            "L4": layer4_reuse(task, variant_trajectory) if "L4" in self.layers else dict(skipped),
        }
        return {
            "task_id": task["id"],
            "domain": task["domain"],
            "profile": trajectory.get("profile"),
            "layers": layers,
            "summary": aggregate(layers),
        }
