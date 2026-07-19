"""
github_mcp.py —— GitHub Issue Creation (default mock, optional real MCP)

- mock (default): renders "Create Issue" as the Issue structure to be submitted, prints it and writes to a local file,
  no network access, no token required.
- real (mock=False, requires GITHUB_TOKEN + GITHUB_REPO): connects to the official
  GitHub MCP Server (stdio) via the MCP protocol, calls its `create_issue` tool to create an Issue in a real repository.
  For safety, real creation must be explicitly enabled by demo.py's --create-issue.
"""

import json
import os
import shlex
from datetime import datetime
from typing import Dict, Any, List

_OUT = os.path.join(os.path.dirname(__file__), "output", "github_issues.json")

# Default startup command for the official GitHub MCP Server (can be overridden with GITHUB_MCP_COMMAND).
# Default runs the official image with Docker; can also be replaced with any MCP Server that exposes the create_issue tool.
_DEFAULT_MCP_COMMAND = (
    "docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server")

# Priority -> GitHub label mapping
_PRIORITY_LABEL = {"P0": "priority:critical", "P1": "priority:high",
                   "P2": "priority:medium", "P3": "priority:low"}


def build_issue(problem: Dict[str, Any], test_cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Renders a diagnostic issue + associated regression test case into a GitHub Issue structure."""
    prio = problem.get("priority", "P2")
    module = problem.get("module", "unknown")
    related = [tc for tc in test_cases
               if tc.get("trajectory_id") in problem.get("trajectory_ids", [])]

    body_lines = [
        f"## Problem Description\n{problem.get('description', '')}",
        f"\n## Involved Modules\n`{module}`",
        f"\n## Priority\n{prio}",
        f"\n## Improvement Suggestions\n{problem.get('suggestion', '')}",
        f"\n## Related Production Traces\n" + ", ".join(problem.get("trajectory_ids", []) or ["(None)"]),
    ]
    if related:
        body_lines.append("\n## Associated Regression Test Cases")
        for tc in related:
            body_lines.append(
                f"- `{tc.get('test_id')}` (Trace {tc.get('trajectory_id')} "
                f"Round {tc.get('focus_turn')}): {tc.get('description', '')}")

    return {
        "title": f"[{prio}][{module}] {problem.get('title', problem.get('description', ''))[:60]}",
        "body": "\n".join(body_lines),
        "labels": [f"module:{module}", _PRIORITY_LABEL.get(prio, "priority:medium"),
                   "auto-diagnosis"],
        "assignees": [problem.get("suggested_assignee", "")] if problem.get("suggested_assignee") else [],
    }


def create_issues(problems: List[Dict[str, Any]], test_cases: List[Dict[str, Any]],
                  mock: bool = True, out_path: str = _OUT,
                  repo: str = None, token: str = None) -> List[Dict[str, Any]]:
    """Create an Issue for each problem.

    mock=True (default): print + write to out_path, no network.
    mock=False: create Issues in a real repository (owner/repo) via GitHub MCP Server, requires token.
    """
    issues = [build_issue(p, test_cases) for p in problems]

    if mock:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        payload = {"created_at": datetime.now().isoformat(),
                   "mode": "mock", "issues": issues}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\n[github_mcp:mock] Wrote {len(issues)} Issues to {out_path}")
        for i, iss in enumerate(issues, 1):
            print(f"\n----- Mock GitHub Issue #{i} -----")
            print(f"title  : {iss['title']}")
            print(f"labels : {iss['labels']}")
            print("body   :")
            for ln in iss["body"].splitlines():
                print("  " + ln)
    else:
        if not token or not repo:
            raise RuntimeError(
                "Real creation requires GITHUB_TOKEN and GITHUB_REPO (owner/repo), see README.")
        created = _create_issues_via_mcp(issues, repo=repo, token=token)
        print(f"\n[github_mcp] Created {repo} Issues via MCP in {len(created)}: ")
        for url in created:
            print(f"    {url}")

    return issues


def _create_issues_via_mcp(issues: List[Dict[str, Any]], repo: str, token: str) -> List[str]:
    """Connect to the official GitHub MCP Server via stdio, call create_issue tool one by one.

    Returns a list of successfully created Issue URLs. Requires the `mcp` Python SDK and an available
    GitHub MCP Server (default Docker image, startup command can be overridden with GITHUB_MCP_COMMAND).
    """
    import asyncio

    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError as e:  # pragma: no cover - provide clear guidance when dependencies are missing
        raise RuntimeError(
            "Missing MCP client: pip install mcp (and ensure GitHub MCP Server can be started)") from e

    owner, _, name = repo.partition("/")
    if not owner or not name:
        raise RuntimeError(f"GITHUB_REPO must be in the form owner/repo, received: {repo!r}")

    cmd = shlex.split(os.getenv("GITHUB_MCP_COMMAND", _DEFAULT_MCP_COMMAND))
    params = StdioServerParameters(
        command=cmd[0], args=cmd[1:],
        env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token})

    async def _run() -> List[str]:
        urls: List[str] = []
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for iss in issues:
                    result = await session.call_tool("create_issue", {
                        "owner": owner, "repo": name,
                        "title": iss["title"], "body": iss["body"],
                        "labels": iss["labels"],
                        "assignees": iss["assignees"],
                    })
                    # MCP tool returns text content; try to extract Issue URL, otherwise fall back to raw text.
                    text = "".join(getattr(c, "text", "") for c in result.content)
                    url = text
                    try:
                        url = json.loads(text).get("html_url", text)
                    except Exception:
                        pass
                    urls.append(url)
        return urls

    return asyncio.run(_run())
