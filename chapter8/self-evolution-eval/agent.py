"""
Reference the tested Agent (a controllable minimal version of the "self-evolving" Agent).

It is not meant to be a real internet-connected strong Agent, but a "controllable mock": it can produce real/semi-real trajectories according to different profiles,
used to run the four-layer verification harness and demonstrate discrimination.

Key points:
- The tool "creation" step is real: the strong profile actually calls an LLM to generate tool code, which is scored by Layer 3 LLM-as-a-Judge; the weak profile provides a rough stub to show low scores.
- The tool "discovery" step produces good/bad search keywords and library selections according to the profile, for Layer 2 heuristic judgment.
- Tool "reuse" is supported by a shared ToolRegistry: the strong profile checks the registry first on a second similar task, and if found, directly retrieves and reuses (no search); the weak profile always re-searches and rebuilds, for Layer 4 discrimination.

Trajectory schema:
{
  "task_id": str,
  "goal": str,
  "profile": str,
  "steps": [ {"action": "...", ...}, ... ],   # see actions below
  "created_tools": [ {"name": str, "code": str} ],
  "final_answer": str
}
step action values:
  search        {"action":"search","query":str}
  read_web      {"action":"read_web","url":str}
  select_library{"action":"select_library","library":str}
  create_tool   {"action":"create_tool","name":str,"code":str}
  register_tool {"action":"register_tool","name":str}
  retrieve_tool {"action":"retrieve_tool","name":str,"source":"registry"}
  call_tool     {"action":"call_tool","name":str,"args":dict,"result":str}
  final_answer  {"action":"final_answer","text":str}
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from config import Config


# ---------------------------------------------------------------------------
# Tool Registry: the self-evolving Agent persists created tools here for reuse in subsequent tasks
# ---------------------------------------------------------------------------
class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, dict] = {}

    def has(self, name: str) -> bool:
        return name in self._tools

    def register(self, name: str, code: str, task_id: str):
        self._tools[name] = {"code": code, "task_id": task_id}

    def get(self, name: str) -> Optional[dict]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._tools)


# ---------------------------------------------------------------------------
# Agent Profile: parameterizes "good/bad" behavior
# ---------------------------------------------------------------------------
@dataclass
class Profile:
    name: str
    discovery_quality: str  # "good" | "bad"
    tool_quality: str       # "good" (calls LLM to generate) | "sloppy" (rough stub)
    reuse_registry: bool    # Whether to check the registry first for reuse on similar tasks


STRONG = Profile("strong", discovery_quality="good", tool_quality="good", reuse_registry=True)
WEAK = Profile("weak", discovery_quality="bad", tool_quality="sloppy", reuse_registry=False)


_TOOL_GEN_SYSTEM = (
    "You are a senior Python engineer building a reusable utility tool. "
    "Return ONLY a single self-contained Python function (plus its imports). "
    "The function MUST have: a clear docstring (purpose, args, returns, raises), "
    "input validation, and try/except error handling with helpful messages. "
    "No example usage, no markdown fences, code only."
)


def _sloppy_tool_code(tool_name: str, library: str) -> str:
    """ Rough stub used by weak profile: no docstring, no validation, no error handling."""
    top = library.split("(")[0].split(">=")[0].strip().replace("-", "_")
    return (
        f"def {tool_name}(x):\n"
        f"    import {top or 'requests'}\n"
        f"    return {top or 'requests'}.run(x)\n"
    )


def _offline_good_tool_code(task: dict, library: str) -> str:
    """ High-quality tool template used by strong profile in offline mode (with docstring / parameter validation / try-except),
    no LLM call needed, convenient for demonstrating L1/L2/L4 deterministic layers without API Key.

    The template deliberately covers all four dimensions of the L3 Rubric, so even when run online, L3 should score high."""
    top = library.split("(")[0].split(">=")[0].strip().replace("-", "_") or "requests"
    name = task["tool_name"]
    goal = task["goal"].replace('"', "'")
    return (
        f"import {top}\n\n\n"
        f"def {name}(query: str, timeout: int = 30):\n"
        f'    """{goal}\n\n'
        f"    Args:\n"
        f"        query: target identifier (e.g., URL / ID / query string), non-empty string.\n"
        f"        timeout: network request timeout in seconds, must be a positive integer.\n"
        f"    Returns:\n"
        f"        Tool execution result.\n"
        f"    Raises:\n"
        f"        ValueError: raised when parameters are invalid.\n"
        f"        RuntimeError: raised when underlying call fails.\n"
        f'    """\n'
        f"    if not isinstance(query, str) or not query.strip():\n"
        f"        raise ValueError('query must be a non-empty string')\n"
        f"    if not isinstance(timeout, int) or timeout <= 0:\n"
        f"        raise ValueError('timeout must be a positive integer')\n"
        f"    try:\n"
        f"        return {top}.run(query, timeout=timeout)\n"
        f"    except Exception as exc:  # noqa: BLE001\n"
        f"        raise RuntimeError(f'{name} Execution failed: {{exc}}') from exc\n"
    )


class SelfEvolutionAgent:
    """Controllable self-evolving Agent. The same registry is shared across multiple runs to support reuse."""

    def __init__(self, registry: ToolRegistry, model: Optional[str] = None, offline: bool = False):
        self.registry = registry
        self.model = Config.resolve_default_model(model)
        self.offline = offline  # When True, use offline tool templates without calling LLM (for demonstrating deterministic layers without API Key)
        self._client = None  # Lazy loading, only establish connection when actually needed to generate tools

    @property
    def client(self):
        if self._client is None:
            self._client = Config.get_client()
        return self._client

    # -- Real LLM call to generate tool code (input source for Layer 3 judge) --------------
    def _generate_tool_code(self, task: dict, library: str) -> str:
        prompt = (
            f"Write a Python function named `{task['tool_name']}` that accomplishes "
            f"this goal:\n{task['goal']}\n\n"
            f"Prefer using the library `{library}`."
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=Config.TEMPERATURE,
            messages=[
                {"role": "system", "content": _TOOL_GEN_SYSTEM},
                {"role": "user", "content": prompt},
            ],
        )
        code = resp.choices[0].message.content or ""
        # Remove possible markdown code fences
        code = code.strip()
        if code.startswith("```"):
            code = code.split("```", 2)[1]
            if code.startswith("python"):
                code = code[len("python"):]
            code = code.strip("`").strip()
        return code

    # -- Discovery phase: produce search keywords, visit web pages, select libraries -------------------------
    def _discovery_steps(self, task: dict, profile: Profile):
        steps = []
        if profile.discovery_quality == "good":
            kws = task.get("discovery_keywords", [])[:3]
            query = " ".join(kws) if kws else task["goal"]
            steps.append({"action": "search", "query": f"{query} python library"})
            lib = task["reference_solution"]["libraries"][0]
            top = lib.split("(")[0].strip()
            steps.append({"action": "read_web", "url": f"https://pypi.org/project/{top}/"})
            steps.append({"action": "select_library", "library": lib})
            return steps, lib
        else:
            # Bad discovery: vague keywords, and selects an obsolete/paid library
            steps.append({"action": "search", "query": "how to do this quickly easy python"})
            pit = task.get("known_pitfalls", {})
            bad = (pit.get("deprecated_libraries") or pit.get("paid_or_registration_apis") or ["requests"])[0]
            steps.append({"action": "select_library", "library": bad})
            return steps, bad

    # -- Main flow ----------------------------------------------------------
    def run(self, task: dict, profile: Profile, use_variant: bool = False) -> dict:
        """Run a task and return a trajectory. use_variant=True indicates this is a "second similar task" (reuse probe)."""
        goal = task["variant_goal"] if use_variant else task["goal"]
        tool_name = task["tool_name"]
        traj = {
            "task_id": task["id"],
            "goal": goal,
            "profile": profile.name,
            "is_variant": use_variant,
            "steps": [],
            "created_tools": [],
            "final_answer": "",
        }

        # 1) Reuse check: strong profile checks registry first
        if profile.reuse_registry and self.registry.has(tool_name):
            traj["steps"].append({"action": "retrieve_tool", "name": tool_name, "source": "registry"})
            traj["steps"].append({
                "action": "call_tool", "name": tool_name, "args": {"goal": goal},
                "result": "(Reuse registered tool, directly get result)",
            })
            traj["final_answer"] = task["mock_answer"]
            traj["steps"].append({"action": "final_answer", "text": traj["final_answer"]})
            return traj

        # 2) Discovery phase
        disc_steps, library = self._discovery_steps(task, profile)
        traj["steps"].extend(disc_steps)

        # 3) Creation phase
        if profile.tool_quality == "good":
            code = (
                _offline_good_tool_code(task, library)
                if self.offline
                else self._generate_tool_code(task, library)
            )
        else:
            code = _sloppy_tool_code(tool_name, library)
        traj["steps"].append({"action": "create_tool", "name": tool_name, "code": code})
        traj["created_tools"].append({"name": tool_name, "code": code})

        # 4) Registration (for reuse)
        self.registry.register(tool_name, code, task["id"])
        traj["steps"].append({"action": "register_tool", "name": tool_name})

        # 5) Call and give answer
        traj["steps"].append({
            "action": "call_tool", "name": tool_name, "args": {"goal": goal},
            "result": "(Tool execution completed)",
        })
        traj["final_answer"] = task["mock_answer"]
        traj["steps"].append({"action": "final_answer", "text": traj["final_answer"]})
        return traj
