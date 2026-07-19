"""
Minimal Code Interpreter Sandbox: Execute model-generated Python code in a subprocess.

- Runs in an isolated subprocess to avoid polluting the main process and allows forced timeout.
- The subprocess uses the same interpreter as the main program (sys.executable), so python-constraint is pre-installed.
- Captures stdout/stderr and returns them to the model, allowing it to see the solution or error messages.
"""
import subprocess
import sys
import tempfile
import os


def run_python(code: str, timeout: int = 20) -> str:
    """Execute code in a subprocess sandbox and return the combined stdout/stderr text."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, timeout=timeout,
        )
        out = proc.stdout
        if proc.stderr.strip():
            out += "\n[stderr]\n" + proc.stderr
        if not out.strip():
            out = "(Code executed, but no output. Remember to use print() to display results.)"
        return out.strip()
    except subprocess.TimeoutExpired:
        return f"[Error] Code execution timed out (exceeded {timeout} seconds)."
    finally:
        os.unlink(path)


if __name__ == "__main__":
    # Self-test: Solve a simple K&K puzzle using python-constraint
    demo = """
from constraint import Problem
p = Problem()
# True=knight (tells truth), False=knave (lies)
p.addVariable('A', [True, False])
p.addVariable('B', [True, False])
# A says "B is a knave": A's truth value == (B is knave) i.e. A == (not B)
p.addConstraint(lambda a, b: a == (not b), ['A', 'B'])
# B says "We are both not knights": B == (not A and not B)
p.addConstraint(lambda a, b: b == ((not a) and (not b)), ['A', 'B'])
for s in p.getSolutions():
    print({k: 'knight' if v else 'knave' for k, v in s.items()})
"""
    print(run_python(demo))
