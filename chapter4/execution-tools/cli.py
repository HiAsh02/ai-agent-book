#!/usr/bin/env python3
"""Unified command-line entry point for execution tools (Experiment 4-2: Execution Tool MCP Server).

This file provides an argparse command-line interface for listing, individually invoking each execution tool, and running an end-to-end offline demo. It reuses the same set of tool implementations behind server.py, so the command-line behavior is fully consistent with the MCP server.

Tool list (same as server.py):
  file_write        Write file (auto syntax/linter check before writing)
  file_edit         Edit file by search-replace (with diff preview and validation)
  code_interpreter  Multi-language sandbox code execution (dangerous operation approval, long output truncation and persistence)
  virtual_terminal  Shell command execution (dangerous command detection, long output truncation and persistence)
  google_calendar_add  Create Google Calendar event (requires credentials)
  github_create_pr     Create GitHub Pull Request (requires token)

Security mechanisms (corresponding to the "Execution Tools" section in the book):
  - LLM pre-approval: irreversible/dangerous operations are reviewed by an independent LLM before execution
  - Auto-validation: Python syntax is validated locally via compile(); other languages fall back to LLM
  - Long output truncation and persistence: when exceeding threshold, only head and tail lines are kept; full output is saved to a temporary file

Usage examples:
  python cli.py list
  python cli.py demo
  python cli.py code --language python --code "print(2 ** 10)"
  python cli.py shell "python3 --version"
  python cli.py write --path notes.txt --content "hello" --overwrite
  python cli.py --no-approval --no-summarize shell "ls -la"

Commands that do not require an API key: list, demo (offline path), and code/shell/write/edit with approval/summarization/non-Python validation disabled. Scenarios requiring an API key: LLM approval, LLM summarization of long output, non-Python syntax validation. calendar and pr additionally require corresponding external credentials.
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
import textwrap


# ---------------------------------------------------------------------------
#Tool metadata (for display by the `list` subcommand)
# ---------------------------------------------------------------------------
TOOL_CATALOG = [
    ("file_write", "File System", "Write file, auto syntax/linter check before writing"),
    ("file_edit", "File System", "Edit file by search-replace, with diff preview and validation"),
    ("code_interpreter", "General Execution", "Multi-language sandbox code execution (Python/JS/Go/Java/C++/Rust/PHP/Bash)"),
    ("virtual_terminal", "General Execution", "Shell command execution, with dangerous command detection and long output truncation"),
    ("google_calendar_add", "External Systems", "Create Google Calendar event (requires credentials.json)"),
    ("github_create_pr", "External Systems", "Create GitHub Pull Request (requires GITHUB_TOKEN)"),
]


def _apply_global_env(args: argparse.Namespace) -> None:
    """Write global switches into environment variables for config.py to read on import.

    config.Config reads environment variables on module import, so all modules that depend on configuration must be imported after this function executes (tool modules in this file are lazily imported inside functions).
    """
    if args.provider:
        os.environ["PROVIDER"] = args.provider
    if args.workspace:
        os.environ["WORKSPACE_DIR"] = os.path.abspath(args.workspace)
    if args.no_approval:
        os.environ["REQUIRE_APPROVAL_FOR_DANGEROUS_OPS"] = "false"
    if args.no_verify:
        os.environ["AUTO_VERIFY_CODE"] = "false"
    if args.no_summarize:
        os.environ["AUTO_SUMMARIZE_COMPLEX_OUTPUT"] = "false"


def _build_tools():
    """Construct shared tool instances (lazy import to ensure environment variables are ready)."""
    from llm_helper import LLMHelper
    from file_tools import FileTools
    from execution_tools import ExecutionTools
    from external_tools import ExternalTools

    llm_helper = LLMHelper()  # Client created lazily, no API key needed for offline use
    return {
        "llm": llm_helper,
        "file": FileTools(llm_helper),
        "exec": ExecutionTools(llm_helper),
        "external": ExternalTools(llm_helper),
    }


def _print_result(result: dict) -> None:
    """Print tool return results uniformly as JSON."""
    print(json.dumps(result, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------
def cmd_list(args: argparse.Namespace) -> int:
    print("Available execution tools:\n")
    print(f"  {'Tool Name':<20} {'Category':<8} Description")
    print(f"  {'-' * 20} {'-' * 8} {'-' * 40}")
    for name, category, desc in TOOL_CATALOG:
        print(f"  {name:<20} {category:<8} {desc}")
    print("\nUse `python cli.py <subcommand> --help` to see parameters for each tool.")
    print("Use `python cli.py demo` to run the end-to-end offline demo.")
    return 0


def cmd_code(args: argparse.Namespace) -> int:
    code = args.code
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            code = f.read()
    if not code:
        print("Error: Please provide code via --code or --file.", file=sys.stderr)
        return 2

    tools = _build_tools()
    result = asyncio.run(tools["exec"].code_interpreter(
        code=code,
        language=args.language,
        timeout=args.timeout,
        stdin=args.stdin,
    ))
    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_shell(args: argparse.Namespace) -> int:
    tools = _build_tools()
    result = asyncio.run(tools["exec"].virtual_terminal(
        command=args.command,
        timeout=args.timeout,
    ))
    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_write(args: argparse.Namespace) -> int:
    content = args.content
    if args.content_file:
        with open(args.content_file, "r", encoding="utf-8") as f:
            content = f.read()
    if content is None:
        print("Error: Please provide file content via --content or --content-file.", file=sys.stderr)
        return 2

    tools = _build_tools()
    result = asyncio.run(tools["file"].write_file(
        path=args.path,
        content=content,
        overwrite=args.overwrite,
    ))
    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_edit(args: argparse.Namespace) -> int:
    tools = _build_tools()
    result = asyncio.run(tools["file"].edit_file(
        path=args.path,
        search=args.search,
        replace=args.replace,
    ))
    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_calendar(args: argparse.Namespace) -> int:
    tools = _build_tools()
    result = asyncio.run(tools["external"].google_calendar_add(
        summary=args.summary,
        start_time=args.start,
        end_time=args.end,
        description=args.description,
        location=args.location,
    ))
    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_pr(args: argparse.Namespace) -> int:
    tools = _build_tools()
    result = asyncio.run(tools["external"].github_create_pr(
        repo_name=args.repo,
        title=args.title,
        body=args.body,
        head_branch=args.head,
        base_branch=args.base,
    ))
    _print_result(result)
    return 0 if result.get("success") else 1


def cmd_demo(args: argparse.Namespace) -> int:
    """End-to-end offline demo: simulate an Agent using execution tools to complete a small real-world task.

    Scenario: Agent needs to write a word frequency counting script, generate sample data, run the statistics, and then verify the result using shell. The demo covers four security mechanisms: linter validation, dangerous command fail-safe approval, long output truncation and persistence. The entire flow runs offline by default (LLM summarization disabled).
    """
    # Demo runs in an isolated temporary workspace to avoid polluting the current directory.
    workspace = tempfile.mkdtemp(prefix="exec_tools_demo_")
    os.environ["WORKSPACE_DIR"] = workspace
    # Offline mode: disable LLM-based output summarization (truncation persistence does not depend on LLM).
    if "AUTO_SUMMARIZE_COMPLEX_OUTPUT" not in os.environ:
        os.environ["AUTO_SUMMARIZE_COMPLEX_OUTPUT"] = "false"

    tools = _build_tools()
    file_tools = tools["file"]
    exec_tools = tools["exec"]

    def section(title: str) -> None:
        print("\n" + "=" * 64)
        print(title)
        print("=" * 64)

    print(f"Demo workspace:{workspace}")
    print(" (Offline path, no API key required; if key is configured, approval/summarization will use real LLM)")

    async def run() -> None:
        # 1. Write file + auto linter validation (valid code)
        section("1. file_write: Write word frequency statistics script (automatic syntax check)")
        script = textwrap.dedent('''\
            """Count word frequencies in a text file."""
            import sys
            from collections import Counter

            def word_count(path):
                with open(path, encoding="utf-8") as f:
                    words = f.read().split()
                return Counter(words)

            if __name__ == "__main__":
                for word, freq in word_count(sys.argv[1]).most_common(5):
                    print(f"{word}\\t{freq}")
            ''')
        r = await file_tools.write_file("wordcount.py", script, overwrite=True)
        print(f"Result: success={r['success']}, verification={r.get('verification')}")
        print(f"Write: {r.get('path')}")

        # 2. linter intercepts code with syntax errors
        section("2. file_write: Write code with syntax errors (linter should intercept)")
        broken = "def broken(:\n    return 1\n"
        r = await file_tools.write_file("broken.py", broken, overwrite=True)
        print(f"Result: success={r['success']}")
        print(f"Validation feedback: {r.get('error')}")

        # 3. Generate sample data
        section("3. file_write: Generate sample data file")
        sample = "apple banana apple cherry banana apple date cherry banana apple\n"
        r = await file_tools.write_file("data.txt", sample, overwrite=True)
        print(f"Result: success={r['success']}, write {r.get('bytes_written')} bytes")

        # 4. code_interpreter: Run statistics script
        section("4. code_interpreter: Run statistics logic (Python sandbox)")
        analysis = textwrap.dedent('''\
            from collections import Counter
            text = "apple banana apple cherry banana apple date cherry banana apple"
            for word, freq in Counter(text.split()).most_common(3):
                print(f"{word}: {freq}")
            ''')
        r = await exec_tools.code_interpreter(code=analysis, language="python")
        print(f"Result: success={r['success']}, returncode={r.get('returncode')}")
        print("stdout:")
        print(textwrap.indent(r.get("stdout", ""), "  "))

        # 5. virtual_terminal: Verify data file with shell
        section("5. virtual_terminal: Verify data file with shell")
        r = await exec_tools.virtual_terminal(
            command=f"wc -w {workspace}/data.txt && echo '--- Word count completed ---'"
        )
        print(f"Result: success={r['success']}, returncode={r.get('returncode')}")
        print("stdout:")
        print(textwrap.indent(r.get("stdout", ""), "  "))

        # 6. Long output truncation and persistence (offline, no LLM needed)
        section("6. code_interpreter: Automatically truncate and persist long output")
        long_code = "for i in range(1000):\n    print(f'line {i}: ' + 'x' * 20)\n"
        r = await exec_tools.code_interpreter(code=long_code, language="python")
        stdout = r.get("stdout", "")
        print(f"Output lines retained in context: {len(stdout.splitlines())}(original 1000 lines)")
        print(f"Full output persisted to file: {r.get('stdout_file')}")
        print("Tail fragment of output in context: ")
        print(textwrap.indent("\n".join(stdout.splitlines()[-4:]), "  "))

        # 7. Approval of dangerous commands (offline fail-safe / online judged by real LLM)
        section("7. virtual_terminal: Dangerous command triggers approval")
        os.environ["REQUIRE_APPROVAL_FOR_DANGEROUS_OPS"] = "true"
        # The target is a non-existent temporary path, so even if executed, it has no side effects.
        danger = await exec_tools.virtual_terminal(
            command="rm -rf /tmp/exec_tools_demo_nonexistent_path_xyz"
        )
        print(f"Result: success={danger['success']}")
        if danger.get("error"):
            print(f"Description: {danger.get('error')}")
            print("(Approval failed: dangerous command intercepted and not executed. Offline without LLM, rejected by fail-safe;"
                  "online, it may also be rejected by the real LLM as high-risk.)")
        else:
            print("(Approval passed: API key configured, real LLM determined the command targets a non-existent path with no side effects and allowed it.)")

        section("Demo completed")
        print("Covered security mechanisms: automatic linter checks, dangerous command approval, long output truncation and persistence.")
        print(f"Demo artifacts located at:{workspace}")

    asyncio.run(run())
    return 0


# ---------------------------------------------------------------------------
# Parameter parsing
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Unified command-line entry for execution tools (Experiment 4-2: Execution Tool MCP Server).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python cli.py list                     List all execution tools
              python cli.py demo                     Run end-to-end offline demo
              python cli.py code --code "print(6*7)"  Execute Python code
              python cli.py shell "ls -la"            Execute shell command
              python cli.py write --path a.txt --content hi --overwrite
              python cli.py --no-approval shell "echo hello"

            With --no-approval / --no-summarize / --no-verify disabled,
            code/shell/write/edit commands can run fully offline without an API key.
        """),
    )

    # Global switches
    parser.add_argument("--provider", help="LLM provider (overrides PROVIDER, e.g., kimi/doubao/siliconflow/openrouter)")
    parser.add_argument("--workspace", help="Working directory (overrides WORKSPACE_DIR, file operations are restricted to this directory)")
    parser.add_argument("--no-approval", action="store_true", help="Disable LLM pre-approval for dangerous operations")
    parser.add_argument("--no-verify", action="store_true", help="Disable automatic syntax verification for writing files/code")
    parser.add_argument("--no-summarize", action="store_true", help="Disable LLM summarization of long output (still truncates and persists)")

    sub = parser.add_subparsers(dest="command", metavar="<subcommand>")

    p = sub.add_parser("list", help="List all available execution tools")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("demo", help="Run end-to-end offline demo (recommended to try first)")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("code", help="Call code_interpreter to execute code")
    p.add_argument("--code", help="Code string to execute")
    p.add_argument("--file", help="Read code to execute from file")
    p.add_argument("--language", default="python",
                   help="Programming language (python/javascript/typescript/go/java/cpp/rust/php/bash, default python)")
    p.add_argument("--timeout", type=float, default=30.0, help="Execution timeout in seconds (default 30)")
    p.add_argument("--stdin", help="Optional standard input")
    p.set_defaults(func=cmd_code)

    p = sub.add_parser("shell", help="Call virtual_terminal to execute shell command")
    p.add_argument("command", help="Shell command to execute")
    p.add_argument("--timeout", type=int, default=30, help="Timeout in seconds (default 30)")
    p.set_defaults(func=cmd_shell)

    p = sub.add_parser("write", help="Call file_write to write file")
    p.add_argument("--path", required=True, help="File path (relative to working directory or absolute path)")
    p.add_argument("--content", help="File content")
    p.add_argument("--content-file", help="Read content to write from file")
    p.add_argument("--overwrite", action="store_true", help="Allow overwriting existing file")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("edit", help="Call file_edit to edit file by search-replace")
    p.add_argument("--path", required=True, help="File path")
    p.add_argument("--search", required=True, help="Text to search")
    p.add_argument("--replace", required=True, help="Replacement text")
    p.set_defaults(func=cmd_edit)

    p = sub.add_parser("calendar", help="Call google_calendar_add to create a calendar event (credentials required)")
    p.add_argument("--summary", required=True, help="Event title")
    p.add_argument("--start", required=True, help="Start time (ISO 8601, e.g., 2025-10-01T10:00:00)")
    p.add_argument("--end", required=True, help="End time (ISO 8601)")
    p.add_argument("--description", help="Event description")
    p.add_argument("--location", help="Event location")
    p.set_defaults(func=cmd_calendar)

    p = sub.add_parser("pr", help="Call github_create_pr to create a Pull Request (token required)")
    p.add_argument("--repo", required=True, help="Repository name (owner/repo format)")
    p.add_argument("--title", required=True, help="PR title")
    p.add_argument("--body", required=True, help="PR description")
    p.add_argument("--head", required=True, help="Source branch")
    p.add_argument("--base", default="main", help="Target branch (default main)")
    p.set_defaults(func=cmd_pr)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        parser.print_help()
        return 0

    _apply_global_env(args)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
