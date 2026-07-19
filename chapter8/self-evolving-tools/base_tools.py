"""
The "non-tool library" part of the five basic tools: web_search / read_webpage / code_interpreter.

Design principles (corresponding to Experiment 8-5 "Minimal Predefinition, Maximum Self-Evolution"):
- **No domain-specific tools are included** (no get_stock_price, no get_youtube_transcript ...).
- The Agent can only rely on web_search to find open-source libraries/APIs, read_webpage to read documentation,
  and code_interpreter to actually execute code in a subprocess sandbox to verify whether a solution works.
- All outputs are based on "real web results / real execution results", thereby suppressing LLM hallucinations.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Target directory for pip install --target inside the sandbox: third-party packages installed here will persist,
# and subsequent encapsulated tools can directly import them under the same PYTHONPATH.
PROJECT_DIR = Path(__file__).resolve().parent
SANDBOX_PKG_DIR = PROJECT_DIR / ".sandbox_packages"


# --------------------------------------------------------------------------- #
# Tool 1: web_search —— DuckDuckGo (no API key required)
# --------------------------------------------------------------------------- #
def web_search(query: str, num_results: int = 6) -> dict:
    """
    Perform web search using DuckDuckGo (free, no key required).

    Implementation highlights (refer to the style of chapter4/perception-tools):
    - Primary: lite.duckduckgo.com (more stable, less likely to be rate-limited);
    - Fallback: html.duckduckgo.com;
    - With exponential backoff retry, automatically retry when DDG occasionally returns 202 (rate-limited), avoiding "network glitch leads to failure".
    """
    query = (query or "").strip()
    if not query:
        return {"success": False, "error": "search query is empty", "results": []}

    num_results = max(1, min(int(num_results), 10))
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15"
        )
    }

    last_err = None
    # Retry each endpoint several times
    for endpoint in ("https://lite.duckduckgo.com/lite/", "https://html.duckduckgo.com/html/"):
        for attempt in range(3):
            try:
                resp = requests.post(
                    endpoint, data={"q": query, "kl": "wt-wt"}, headers=headers, timeout=15
                )
                if resp.status_code == 202:  # DDG rate-limit signal
                    raise RuntimeError("rate limited (202)")
                resp.raise_for_status()
                results = _parse_ddg(endpoint, resp.text, num_results)
                if results:
                    return {"success": True, "query": query, "count": len(results), "results": results}
                last_err = "no results parsed"
            except Exception as e:  # noqa: BLE001
                last_err = str(e)
            time.sleep(1.5 * (attempt + 1))  # Backoff

    return {"success": False, "error": f"search failed: {last_err}", "results": []}


def _parse_ddg(endpoint: str, html: str, num_results: int) -> list:
    """ Parse two page structures of DuckDuckGo."""
    soup = BeautifulSoup(html, "html.parser")
    results = []

    if "html.duckduckgo" in endpoint:
        for div in soup.find_all("div", class_="result")[:num_results]:
            a = div.find("a", class_="result__a")
            if not a:
                continue
            snip = div.find("a", class_="result__snippet")
            results.append(
                {
                    "title": a.get_text(strip=True),
                    "url": a.get("href", ""),
                    "snippet": snip.get_text(strip=True) if snip else "",
                }
            )
    else:  # Lite version: results are plain <a href="http...">
        for a in soup.find_all("a"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            if href.startswith("http") and text:
                results.append({"title": text, "url": href, "snippet": ""})
            if len(results) >= num_results:
                break
    return results


# --------------------------------------------------------------------------- #
# Tool 2: read_webpage —— Fetch web page and extract main content
# --------------------------------------------------------------------------- #
def read_webpage(url: str, max_chars: int = 6000) -> dict:
    """Fetch a web page and extract plain text content for the Agent to read README / API documentation."""
    if not url or not url.startswith(("http://", "https://")):
        return {"success": False, "error": "invalid url"}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return {"success": False, "error": f"fetch failed: {e}", "url": url}

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
    truncated = len(text) > max_chars
    return {
        "success": True,
        "url": url,
        "title": soup.title.get_text(strip=True) if soup.title else "",
        "text": text[:max_chars],
        "truncated": truncated,
    }


# --------------------------------------------------------------------------- #
# Tool 3: code_interpreter —— Execute Python in a subprocess sandbox
# --------------------------------------------------------------------------- #
def code_interpreter(code: str, pip_install: list | None = None, timeout: int = 60) -> dict:
    """
    Execute Python code in an **independent subprocess** (sandbox) to verify libraries/APIs found online.

    - pip_install: list of third-party packages to install first; install to temporary directory .sandbox_packages (--target),
      without polluting the system environment, and make them importable by the subprocess via PYTHONPATH.
    - timeout: force termination on timeout to avoid infinite loops / hangs.

    Security boundary reminder: This is a "demo-level" sandbox (process isolation + timeout only), not a security sandbox.
    For production, use containers / gVisor / network-namespace-less strong isolation, and audit packages to install (supply chain risk).
    """
    SANDBOX_PKG_DIR.mkdir(exist_ok=True)
    logs = []

    # Subprocess environment: add sandbox package directory to PYTHONPATH (system site-packages still available)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SANDBOX_PKG_DIR) + os.pathsep + env.get("PYTHONPATH", "")

    # 1) pip install --target as needed
    if pip_install:
        for pkg in pip_install:
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet",
                     "--target", str(SANDBOX_PKG_DIR), pkg],
                    capture_output=True, text=True, timeout=180, env=env,
                )
                if r.returncode != 0:
                    logs.append(f"[pip install {pkg}] FAILED: {r.stderr.strip()[-500:]}")
                else:
                    logs.append(f"[pip install {pkg}] ok")
            except Exception as e:  # noqa: BLE001
                logs.append(f"[pip install {pkg}] error: {e}")

    # 2) Execute code
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, dir=SANDBOX_PKG_DIR) as f:
        f.write(code)
        script = f.name
    try:
        r = subprocess.run(
            [sys.executable, script],
            capture_output=True, text=True, timeout=timeout, env=env,
        )
        out = r.stdout[-8000:]
        result = {
            "success": r.returncode == 0,
            "stdout": out,
            "stderr": r.stderr[-4000:],
            "returncode": r.returncode,
            "pip_logs": logs,
        }
        # Remind the model: running successfully but without any print output means no real data was obtained; cannot answer or encapsulate tools based on that.
        if r.returncode == 0 and not out.strip():
            result["note"] = (
                "Code executed successfully but stdout is empty — you did not print any real data."
                "This does not count as verification passed: please modify the code to actually call the library and print real numbers."
            )
        return result
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"timeout after {timeout}s", "pip_logs": logs}
    finally:
        try:
            os.unlink(script)
        except OSError:
            pass


def run_python_snippet(code: str, timeout: int = 60) -> dict:
    """For reuse by tool_manager: execute a script in the same sandbox environment and return the result (without pip)."""
    return code_interpreter(code, pip_install=None, timeout=timeout)
