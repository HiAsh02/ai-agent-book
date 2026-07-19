"""
Tool implementation and tool set definition.

This file contains two parts:
1. Workspace: an in-process "virtual workspace" that stores requirements and file contents,
   and provides real code execution / syntax checking / complexity analysis capabilities.
2. The JSON Schema for tools in each of the three phases (for OpenAI function calling).

Key point: the tool sets exposed to the model differ across phases. This is a core aspect of the "phased system prompt" experiment—the prompt changes roles, and the tools switch accordingly.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from typing import Dict, List


# ----------------------------------------------------------------------------
# Name of the "signal tool" that triggers phase transitions. The agent main loop switches phases when it sees these tools being called.
# ----------------------------------------------------------------------------
COMPLETE_REQUIREMENTS = "complete_requirements_analysis"  # Phase 1 -> Phase 2
SUBMIT_FOR_REVIEW = "submit_for_review"                   # Phase 2 -> Phase 3
REQUEST_REVISION = "request_revision"                     # Phase 3 -> Phase 2 (rollback)
APPROVE_CODE = "approve_code"                             # Phase 3 -> Complete


class Workspace:
    """ Cross-phase shared task state (requirements, files, review comments)."""

    def __init__(self) -> None:
        # Confirmed requirements collected in Phase 1 (key -> value)
        self.requirements: Dict[str, str] = {}
        # "File system" written in Phase 2 (path -> content)
        self.files: Dict[str, str] = {}
        # List of issues recorded during Phase 3 rollback, for reference when Phase 2 fixes them
        self.review_issues: List[str] = []

    # --- Phase 1: Requirements Analyst Tool Implementation -------------------------------------
    def save_requirement(self, key: str, value: str) -> str:
        self.requirements[key] = value
        return f"Recorded requirement [{key}] = {value}"

    # --- Phase 2: Software Engineer Tool Implementation -------------------------------------
    def write_file(self, path: str, content: str) -> str:
        self.files[path] = content
        return f"Written file {path}（{len(content)} characters, {content.count(chr(10)) + 1} lines)"

    def read_file(self, path: str) -> str:
        if path not in self.files:
            return f"Error: file {path} does not exist. Current file list:{list(self.files) or 'empty'}"
        return self.files[path]

    def execute_code(self, code: str) -> str:
        """Actually execute a piece of Python in a temporary directory and return stdout/stderr (with timeout)."""
        return _run_python_source(code)

    # --- Phase 3: Code Reviewer Tool Implementation -------------------------------------
    def run_linter(self, path: str) -> str:
        """Lightweight static check: syntax compilation + common code smells, no extra dependencies."""
        if path not in self.files:
            return f"Error: file {path} does not exist."
        source = self.files[path]
        problems: List[str] = []

        # 1) Whether syntax compiles
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return f"[linter] Syntax error: line {exc.lineno} {exc.msg}"

        # 2) Line-by-line style issues (threshold set to "strict but achievable", convenient for demo: first rollback then pass)
        for i, line in enumerate(source.splitlines(), start=1):
            if len(line) > 120:
                problems.append(f"L{i}: line exceeds 120 characters ({len(line)}), please wrap or simplify")
            if line.rstrip() != line:
                problems.append(f"L{i}: trailing whitespace at end of line")
            if "\t" in line:
                problems.append(f"L{i}: Uses tab indentation, spaces are recommended")

        # 3) AST-based issues: missing module docstring, bare except
        if not ast.get_docstring(tree):
            problems.append("Module is missing a file-level docstring (please add a triple-quoted description at the beginning of the file)")
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                problems.append(f"L{node.lineno}: Uses bare except, it is recommended to catch specific exceptions")

        if not problems:
            return "[linter] Passed: no issues found."
        return "[linter] Found %d issues: \n- %s" % (len(problems), "\n- ".join(problems))

    def run_tests(self, path: str) -> str:
        """Smoke test: run the file to verify that import / main flow does not crash."""
        if path not in self.files:
            return f"Error: file {path} does not exist."
        # Create a fake "download folder" so the organizing script has something to organize
        harness = (
            "import os, tempfile, runpy, sys\n"
            "d = tempfile.mkdtemp()\n"
            "for name in ['a.jpg','b.pdf','c.txt','d.mp3','readme']:\n"
            "    open(os.path.join(d, name), 'w').close()\n"
            "sys.argv = ['script', d]\n"
            "print('SMOKE_TEST target dir:', d)\n"
            + self.files[path]
        )
        result = _run_python_source(harness)
        ok = "Traceback" not in result and "Error" not in result
        verdict = "PASS" if ok else "FAIL"
        return f"[tests] Smoke test results:{verdict}\n{result}"

    def analyze_complexity(self, path: str) -> str:
        """Estimate complexity using AST: number of functions, maximum branch count, maximum nesting depth."""
        if path not in self.files:
            return f"Error: file {path} does not exist."
        try:
            tree = ast.parse(self.files[path])
        except SyntaxError as exc:
            return f"[complexity] Unable to parse:{exc.msg}"

        funcs = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        branch_types = (ast.If, ast.For, ast.While, ast.Try, ast.With)
        total_branches = sum(1 for n in ast.walk(tree) if isinstance(n, branch_types))

        def depth(node: ast.AST, level: int = 0) -> int:
            best = level
            for child in ast.iter_child_nodes(node):
                inc = 1 if isinstance(child, branch_types) else 0
                best = max(best, depth(child, level + inc))
            return best

        return (
            "[complexity] Number of functions=%d, branch/loop statements=%d, maximum nesting depth=%d"
            % (len(funcs), total_branches, depth(tree))
        )


def _run_python_source(source: str, timeout: int = 10) -> str:
    """Write the source code to a temporary file and execute it in a subprocess, returning the combined output."""
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "snippet.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(source)
        try:
            proc = subprocess.run(
                [sys.executable, script],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return f"Execution timed out (>{timeout}s）"
        out = (proc.stdout or "").strip()
        err = (proc.stderr or "").strip()
        parts = []
        if out:
            parts.append("stdout:\n" + out)
        if err:
            parts.append("stderr:\n" + err)
        parts.append(f"Exit code: {proc.returncode}")
        return "\n".join(parts)


# ----------------------------------------------------------------------------
# Tool schemas for each phase (OpenAI tools format). Each phase only exposes its own set of tools.
# ----------------------------------------------------------------------------

def _tool(name: str, description: str, properties: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


STAGE1_TOOLS = [
    _tool(
        "ask_clarifying_question",
        "Ask the user a clarifying question about requirements; the user will answer. Must clarify when requirements are unclear.",
        {"question": {"type": "string", "description": "Question to ask the user"}},
        ["question"],
    ),
    _tool(
        "save_requirement",
        "Record a confirmed requirement into the requirements document for use in the subsequent implementation phase.",
        {
            "key": {"type": "string", "description": "Requirement item name, e.g., file_types"},
            "value": {"type": "string", "description": "Requirement item value/description"},
        },
        ["key", "value"],
    ),
    _tool(
        COMPLETE_REQUIREMENTS,
        "Called when all key requirements have been clarified and recorded, ending the requirements analysis phase and entering the code implementation phase.",
        {"summary": {"type": "string", "description": "One-sentence summary of the confirmed requirements"}},
        ["summary"],
    ),
]

STAGE2_TOOLS = [
    _tool(
        "write_file",
        "Write (or overwrite) the full content of a file.",
        {
            "path": {"type": "string", "description": "File path, e.g., organize_downloads.py"},
            "content": {"type": "string", "description": "Full content of the file"},
        },
        ["path", "content"],
    ),
    _tool(
        "read_file",
        "Read the content of an already written file.",
        {"path": {"type": "string", "description": "File path"}},
        ["path"],
    ),
    _tool(
        "execute_code",
        "Execute a piece of Python code for self-testing/verification, returning stdout and stderr.",
        {"code": {"type": "string", "description": "Python code to execute"}},
        ["code"],
    ),
    _tool(
        SUBMIT_FOR_REVIEW,
        "Called when the code implementation is complete and self-testing passes, to submit to the code reviewer for review.",
        {"file": {"type": "string", "description": "The main file path to be submitted for review."}},
        ["file"],
    ),
]

STAGE3_TOOLS = [
    _tool(
        "run_linter",
        "Run static checks on the file and return code style/specification issues.",
        {"file": {"type": "string", "description": "File path"}},
        ["file"],
    ),
    _tool(
        "run_tests",
        "Run smoke tests on the file to verify it can run normally.",
        {"file": {"type": "string", "description": "File path"}},
        ["file"],
    ),
    _tool(
        "analyze_complexity",
        "Analyze the code complexity of the file (number of functions, branches, nesting depth).",
        {"file": {"type": "string", "description": "File path"}},
        ["file"],
    ),
    _tool(
        REQUEST_REVISION,
        "Called when the review finds issues that must be fixed, to return the code to the implementation phase with a list of issues.",
        {
            "issues": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of issues that need to be fixed.",
            }
        },
        ["issues"],
    ),
    _tool(
        APPROVE_CODE,
        "Called when the code passes all reviews and meets quality standards, to approve the code and complete the task.",
        {"comment": {"type": "string", "description": "Brief comment on passing the review."}},
        ["comment"],
    ),
]
