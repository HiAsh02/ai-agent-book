"""
tester.py — automated testing (structural assertions on the generated parser)

The original approach in the book: render the generated visualization code in a virtual browser, then use a Vision LLM to inspect the image.
Since there is no playwright/browser on this machine, we **downgrade** to unit testing the parse function:
feed a batch of sample logs to the generated parse function and assert that it can parse the expected structured fields.
This ensures that "the generated code can indeed correctly parse the new format", serving as the real quality gate in the self-healing loop.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

ParserFn = Callable[[str], Optional[Dict]]


def run_tests(
    parse_fn: ParserFn,
    samples: List[str],
    required_keys: List[str],
) -> Dict:
    """Run a set of assertions on parse_fn, returning {passed: bool, report: str, results: [...]}.

    Pass conditions (must hold for every sample):
      1. parse_fn(line) does not throw an exception;
      2. The return value is a non-empty dict;
      3. Every field in required_keys exists and its value is not empty (not None, not empty string).
    """
    lines: List[str] = []
    results: List[Optional[Dict]] = []
    all_passed = True

    for i, sample in enumerate(samples, 1):
        try:
            out = parse_fn(sample)
        except Exception as exc:  #The generated code crashed directly on the sample
            all_passed = False
            results.append(None)
            lines.append(f"[Sample {i}] Parsing threw an exception: {type(exc).__name__}: {exc}")
            continue

        if not isinstance(out, dict) or not out:
            all_passed = False
            results.append(out)
            lines.append(f"[Sample {i}] Did not return a non-empty dict, actual return: {out!r}")
            continue

        missing = [k for k in required_keys if k not in out or out[k] in (None, "")]
        if missing:
            all_passed = False
            lines.append(
                f"[Sample {i}] Missing/empty required fields: {missing}; actual parsed: {out}"
            )
        else:
            lines.append(f"[Sample {i}] Passed, parsed fields: {sorted(out.keys())}")
        results.append(out)

    report = "\n".join(lines)
    return {"passed": all_passed, "report": report, "results": results}
