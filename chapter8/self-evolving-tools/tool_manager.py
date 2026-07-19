"""
Tool library management: create_tool (encapsulate and persist), search_tools (retrieve and reuse), and execution of encapsulated tools.

This is the core of Alita-style "self-evolution":
- After an Agent validates a solution with code_interpreter, it calls create_tool to solidify it into a
  "standard tool" — containing name / description / JSON-Schema parameters / Python code, persisted to tool_library/.
- Next time a similar task arises, the Agent should search_tools to hit an existing tool and reuse it directly, instead of searching the web again and rewriting code.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
LIBRARY_DIR = PROJECT_DIR / "tool_library"
SANDBOX_PKG_DIR = PROJECT_DIR / ".sandbox_packages"


def normalize_schema(params) -> dict:
    """
    Normalize the parameters given by the model into a valid OpenAI function-calling JSON Schema.
    Common model mistake: only providing the properties mapping while omitting the top-level {"type":"object"}. Here we tolerate this error,
    otherwise exposing such a tool to OpenAI would trigger a 400 invalid schema and interrupt the entire flow.
    """
    if not isinstance(params, dict):
        return {"type": "object", "properties": {}}
    if params.get("type") == "object" and "properties" in params:
        return params
    if "properties" in params:  #  Has properties but type is missing/incorrect
        out = {"type": "object", "properties": params["properties"]}
        if "required" in params:
            out["required"] = params["required"]
        return out
    #  Treat the entire dict as the properties mapping
    return {"type": "object", "properties": params}


class ToolLibrary:
    """A minimal file-based tool library. Each tool = one .json (metadata + code)."""

    def __init__(self, library_dir: Path = LIBRARY_DIR):
        self.dir = Path(library_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------- create_tool ----------------------------- #
    def create_tool(self, name: str, description: str, parameters: dict, code: str,
                    test_args: dict | None = None) -> dict:
        """
        Encapsulate a function as a standard tool and persist it.

        Convention: the code must define a function named run(**kwargs) that returns a JSON-serializable result.
        parameters is an OpenAI function-calling style JSON Schema (type=object, properties, required).

        "Pre-persistence validation" gate (corresponding to the "test" step in Figure 8-7 pipeline and the "tool quality degradation" warning in this chapter):
        - First perform **syntax compilation check**; code with syntax errors is rejected from the library;
        - If test_args is provided, **actually execute run(**test_args)** in a sandbox; only if it returns successfully
          is registration allowed — thus preventing "encapsulated but non-functional" bad tools from polluting the tool library and being reused by subsequent tasks.
        """
        name = name.strip()
        if not name.isidentifier():
            return {"success": False, "error": f"invalid tool name: {name!r} (must be a valid identifier)"}
        if "def run" not in code:
            return {"success": False, "error": "tool code must define a function `def run(**kwargs)`"}
        #  Pre-persistence validation 1: syntax compilation check (bad syntax is blocked outside the library)
        try:
            compile(code, f"<tool {name}>", "exec")
        except SyntaxError as e:
            return {"success": False, "error": f"tool code has a syntax error: {e}"}

        record = {
            "name": name,
            "description": description,
            "parameters": normalize_schema(parameters),
            "code": code,
        }

        #  Pre-persistence validation 2: if test_args is given, actually run run() once; if it fails, reject registration
        validated = False
        if test_args is not None:
            val = self._run_record(record, test_args)
            if not val.get("success"):
                return {
                    "success": False,
                    "error": "Tool registration pre-validation failed: run(**test_args) did not return successfully. Please fix the code or test_args"
                             "and resubmit (tools that fail validation will not be added to the library, to prevent bad tools from being reused by subsequent tasks).",
                    "validation": val,
                }
            validated = True

        (self.dir / f"{name}.json").write_text(json.dumps(record, ensure_ascii=False, indent=2))
        return {
            "success": True,
            "message": f"tool '{name}' created and saved to tool_library/"
                       + ("(Passed pre-persistence validation)" if validated else "(No test_args provided, skipping runtime validation)"),
            "name": name,
            "validated": validated,
        }

    # ----------------------------- search_tools ---------------------------- #
    def search_tools(self, query: str) -> dict:
        """Keyword search by name/description, returning matched tools (for reuse)."""
        query = (query or "").strip().lower()
        terms = [t for t in query.replace(",", " ").split() if t]
        hits = []
        for rec in self.list_tools():
            haystack = (rec["name"] + " " + rec["description"]).lower()
            score = sum(1 for t in terms if t in haystack)
            if score > 0 or not terms:
                hits.append((score, rec))
        hits.sort(key=lambda x: -x[0])
        return {
            "success": True,
            "query": query,
            "count": len(hits),
            "tools": [
                {"name": r["name"], "description": r["description"], "parameters": r["parameters"]}
                for _, r in hits
            ],
        }

    # ------------------------------ helpers -------------------------------- #
    def list_tools(self) -> list:
        recs = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                recs.append(json.loads(p.read_text()))
            except Exception:  # noqa: BLE001
                continue
        return recs

    def get_tool(self, name: str) -> dict | None:
        p = self.dir / f"{name}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text())

    # -------------------------- execute a wrapped tool --------------------- #
    def execute_tool(self, name: str, arguments: dict, timeout: int = 60) -> dict:
        """
        Execute an encapsulated tool in a child process sandbox: inject code + run(**args), capture JSON result.
        PYTHONPATH points to .sandbox_packages, making dependencies installed during create available.
        """
        rec = self.get_tool(name)
        if rec is None:
            return {"success": False, "error": f"tool '{name}' not found in library"}
        return self._run_record(rec, arguments, timeout)

    def _run_record(self, rec: dict, arguments: dict, timeout: int = 60) -> dict:
        """Execute run(**arguments) in a sandbox child process using the tool record (including code).

        Directly consumes the record without reading disk, so it can be used for "pre-persistence validation" even before the tool is written to disk.
        """
        SANDBOX_PKG_DIR.mkdir(exist_ok=True)
        driver = (
            rec["code"]
            + "\n\nif __name__ == '__main__':\n"
            "    import json as _json, sys as _sys\n"
            "    _args = _json.loads(_sys.argv[1])\n"
            "    _out = run(**_args)\n"
            "    print('__TOOL_RESULT__' + _json.dumps(_out, default=str))\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(SANDBOX_PKG_DIR) + os.pathsep + env.get("PYTHONPATH", "")

        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=SANDBOX_PKG_DIR) as f:
            f.write(driver)
            script = f.name
        try:
            r = subprocess.run(
                [sys.executable, script, json.dumps(arguments)],
                capture_output=True, text=True, timeout=timeout, env=env,
            )
            if r.returncode != 0:
                return {"success": False, "error": "tool crashed", "stderr": r.stderr[-3000:]}
            for line in r.stdout.splitlines():
                if line.startswith("__TOOL_RESULT__"):
                    return {"success": True, "result": json.loads(line[len("__TOOL_RESULT__"):])}
            return {"success": False, "error": "no result marker", "stdout": r.stdout[-2000:]}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"timeout after {timeout}s"}
        finally:
            try:
                os.unlink(script)
            except OSError:
                pass
