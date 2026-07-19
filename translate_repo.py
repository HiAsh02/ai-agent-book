#!/usr/bin/env python3
"""Translate Chinese text in this repository to English, in place.

The script walks the repository (using ``git ls-files`` by default), finds every
text file that still contains Chinese characters, and rewrites it through an
OpenAI-compatible chat-completions API (DeepSeek, OpenAI, Kimi, OpenRouter, ...).

Design goals
------------
* Structure preserving  - only natural-language Chinese is translated. Code,
  identifiers, Markdown/HTML/JSON structure, URLs, file paths and whitespace are
  copied verbatim. Long files are split on line boundaries so reconstruction is
  byte-accurate outside the translated spans.
* Resumable             - a JSON state file records the hash of each translated
  result, so re-runs skip files that are already done and unchanged. Files that
  no longer contain Chinese are skipped automatically.
* Concurrent            - a thread pool issues API calls in parallel.
* Safe                  - never reads or writes ``.env`` files, binaries,
  lockfiles, the virtualenv, the state file or this script itself. The API key
  is read from the environment and is never written to disk.

Usage
-----
    export DEEPSEEK_API_KEY=sk-...
    python translate_repo.py --list            # show what would be translated
    python translate_repo.py --limit 5         # translate a small sample first
    python translate_repo.py                    # translate everything (resumable)

Run ``python translate_repo.py --help`` for all options.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fnmatch
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    sys.exit("The 'openai' package is required. Install with: pip install openai")

import re

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# CJK ideographs (Unified + Extension A + compatibility) - enough to detect
# Chinese text. We deliberately do not include kana/hangul.
CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002a6df]")

# File extensions we never translate (binary / data / vendored artefacts).
SKIP_EXTS = {
    # video / audio / images (SVG is intentionally NOT here - it holds text)
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4a", ".mp3", ".wav", ".flac",
    ".ogg", ".aac", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp",
    ".tiff", ".psd",
    # documents / archives
    ".pdf", ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
    # fonts
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    # ML / data blobs
    ".onnx", ".parquet", ".tiktoken", ".bin", ".pt", ".pth", ".safetensors",
    ".npy", ".npz", ".h5", ".hdf5", ".pkl", ".pickle", ".model", ".arrow",
    # compiled / lock artefacts
    ".pyc", ".pyo", ".so", ".dylib", ".dll", ".class", ".o", ".a", ".lock",
    ".min.js", ".min.css", ".map",
}

# Exact filenames we never touch (lockfiles etc.). ``.env`` handling is special
# and done in ``is_secret_file``.
SKIP_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "uv.lock", "composer.lock", "Gemfile.lock",
}

# Directory names skipped when walking without git (``--all-files``).
SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "dist", "build", ".next", ".turbo", ".cache",
    ".idea", ".vscode", "site-packages",
}

# Per-extension context hints given to the model so it knows the file grammar.
TYPE_HINTS = {
    ".md": "Markdown documentation",
    ".mdx": "MDX documentation (Markdown + JSX)",
    ".py": "Python source code",
    ".ts": "TypeScript source code",
    ".tsx": "TypeScript React (TSX) source code",
    ".js": "JavaScript source code",
    ".jsx": "JavaScript React (JSX) source code",
    ".svg": "SVG vector image (translate ONLY the visible text inside <text>/<tspan>/<title> and human-facing attributes)",
    ".json": "JSON data (translate ONLY human-readable string values; keep object keys and identifier-like values unchanged)",
    ".jsonl": "JSON Lines data (translate ONLY human-readable string values; keep keys unchanged)",
    ".yaml": "YAML config (translate ONLY comments and human-readable string values; keep keys unchanged)",
    ".yml": "YAML config (translate ONLY comments and human-readable string values; keep keys unchanged)",
    ".toml": "TOML config (translate ONLY comments and human-readable string values; keep keys unchanged)",
    ".ini": "INI config (translate ONLY comments and human-readable values; keep keys unchanged)",
    ".html": "HTML (translate ONLY visible text and human-facing attributes such as title/alt/placeholder)",
    ".htm": "HTML (translate ONLY visible text and human-facing attributes such as title/alt/placeholder)",
    ".xml": "XML (translate ONLY visible text content and human-facing attribute values)",
    ".sql": "SQL (translate ONLY comments and human-facing string literals; keep identifiers)",
    ".sh": "Shell script (translate ONLY comments and human-facing echoed strings)",
    ".tex": "LaTeX (translate prose; keep commands, math, labels and references)",
    ".lua": "Lua source code",
    ".css": "CSS stylesheet (translate ONLY comments and content strings)",
    ".less": "LESS stylesheet (translate ONLY comments and content strings)",
    ".txt": "plain text",
    ".example": "example config file (translate ONLY comments and human-readable values; keep keys and placeholders)",
    ".template": "template config file (translate ONLY comments and human-readable values; keep keys and placeholders)",
    ".sample": "sample config file (translate ONLY comments and human-readable values; keep keys and placeholders)",
}

SYSTEM_PROMPT = """\
You are a professional software-localization engine. You translate Simplified and \
Traditional Chinese into clear, natural, technically accurate English.

You are given the contents (or a fragment) of a source file. The file type is: {filetype}.

TRANSLATE
- All Chinese natural-language text: prose, headings, comments, docstrings,
  human-facing string literals, UI labels, log/print messages, and text inside
  diagrams or figures.
- Produce fluent, idiomatic technical English (meaning-for-meaning, not literal).
- Keep terminology consistent. Preferred glossary:
  智能体/代理->agent, 多智能体->multi-agent, 上下文->context, 上下文工程->context engineering,
  提示词/提示->prompt, 提示工程->prompt engineering, 大模型/大语言模型->LLM, 模型->model,
  工具调用->tool call, 检索->retrieval, 检索增强生成->RAG, 向量->vector, 嵌入->embedding,
  记忆->memory, 微调->fine-tuning, 强化学习->reinforcement learning, 推理->inference/reasoning,
  智能体技能->agent skill, 知识库->knowledge base, 章节->chapter, 实验->experiment.

DO NOT CHANGE (copy verbatim, byte for byte)
- Code structure, syntax, indentation and ALL whitespace. Never reflow or reindent.
- Programming identifiers: variable/function/class/module names, keywords, decorators.
- Import paths, file paths, URLs, environment-variable names, CLI flags, hashes, IDs.
- Markdown/HTML/XML/JSON/YAML structure and syntax; translate only the human text.
- Code fences and the code inside them, EXCEPT translate comments and human-facing
  strings that appear within that code.
- LaTeX and math, numbers, dates, and anything already written in English.

OUTPUT RULES (critical)
- Output ONLY the translated file content. No preamble, no explanation, no notes.
- Do NOT wrap the whole output in a Markdown code fence.
- Preserve the exact leading and trailing whitespace, including the final newline.
- The output must be structurally identical to the input with Chinese replaced by English.\
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()


def is_secret_file(name: str) -> bool:
    """True for real dotenv secret files, but not for *.example/template/sample."""
    if name == ".env":
        return True
    if name.startswith(".env.") and not name.endswith(
        (".example", ".template", ".sample")
    ):
        return True
    return False


def has_chinese(text: str) -> bool:
    return CJK_RE.search(text) is not None


def type_hint(path: Path) -> str:
    return TYPE_HINTS.get(path.suffix.lower(), "plain text / config")


def read_text(path: Path) -> Optional[str]:
    """Return UTF-8 text, or None if the file is binary/undecodable/too odd."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def split_budget(text: str, budget: int) -> list[str]:
    """Split text into fragments <= ``budget`` chars on line boundaries.

    Concatenating the returned fragments reproduces ``text`` exactly. A single
    line longer than ``budget`` becomes its own (over-budget) fragment.
    """
    lines = text.splitlines(keepends=True)
    parts: list[str] = []
    cur: list[str] = []
    cur_len = 0
    for ln in lines:
        if cur and cur_len + len(ln) > budget:
            parts.append("".join(cur))
            cur, cur_len = [], 0
        cur.append(ln)
        cur_len += len(ln)
    if cur:
        parts.append("".join(cur))
    return parts or [text]


def strip_wrapping_fence(src: str, out: str) -> str:
    """Remove a Markdown code fence the model may have wrapped the output in."""
    if src.lstrip().startswith("```"):
        return out  # the source legitimately starts with a fence
    stripped = out.strip()
    if stripped.startswith("```") and stripped.endswith("```") and len(stripped) > 6:
        nl = stripped.find("\n")
        if nl != -1:
            inner = stripped[nl + 1:]
            last = inner.rfind("```")
            if last != -1:
                return inner[:last].rstrip("\n")
    return out


def match_globs(rel: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, g) for g in globs)


# --------------------------------------------------------------------------- #
# Translator
# --------------------------------------------------------------------------- #

@dataclass
class Translator:
    client: OpenAI
    model: str
    temperature: float = 0.2
    max_output_tokens: int = 8192
    max_chars: int = 6000
    max_retries: int = 5
    min_chunk: int = 400

    def _call(self, system: str, user: str) -> tuple[str, str]:
        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                choice = resp.choices[0]
                content = choice.message.content or ""
                if not content.strip():
                    raise RuntimeError("empty response from model")
                return content, (choice.finish_reason or "stop")
            except Exception as exc:  # noqa: BLE001 - surface after retries
                last_err = exc
                time.sleep(min(2 ** attempt, 30))
        raise RuntimeError(f"API call failed after {self.max_retries} retries: {last_err}")

    def _fragment(self, text: str, filetype: str, depth: int = 0) -> str:
        if not has_chinese(text):
            return text
        system = SYSTEM_PROMPT.format(filetype=filetype)
        content, finish = self._call(system, text)
        if finish == "length" and depth < 6 and len(text) > self.min_chunk:
            parts = split_budget(text, max(len(text) // 2, self.min_chunk))
            if len(parts) > 1:
                return "".join(self._fragment(p, filetype, depth + 1) for p in parts)
            # a single over-long line: fall back to a hard character split
            mid = len(text) // 2
            return self._fragment(text[:mid], filetype, depth + 1) + self._fragment(
                text[mid:], filetype, depth + 1
            )
        return strip_wrapping_fence(text, content)

    def translate(self, text: str, filetype: str) -> tuple[str, int]:
        """Translate a whole file. Returns (new_text, num_chunks)."""
        if len(text) <= self.max_chars:
            out = self._fragment(text, filetype)
            chunks = 1
        else:
            parts = split_budget(text, self.max_chars)
            out = "".join(self._fragment(p, filetype) for p in parts)
            chunks = len(parts)
        # keep the original trailing-newline convention
        if text.endswith("\n") and not out.endswith("\n"):
            out += "\n"
        elif not text.endswith("\n") and out.endswith("\n"):
            out = out.rstrip("\n")
        return out, chunks

    def cleanup(self, text: str, filetype: str) -> tuple[str, int]:
        """Re-translate ONLY the lines that still contain Chinese.

        Lines without Chinese are preserved byte-for-byte, so this is a cheap,
        surgical pass that fixes residual misses without churning good English.
        Returns (new_text, num_blocks_translated).
        """
        lines = text.splitlines(keepends=True)
        flags = [has_chinese(ln) for ln in lines]
        out: list[str] = []
        i, n, blocks = 0, len(lines), 0
        while i < n:
            if not flags[i]:
                out.append(lines[i])
                i += 1
                continue
            j = i
            while j < n and flags[j]:
                j += 1
            block = "".join(lines[i:j])
            blocks += 1
            if len(block) <= self.max_chars:
                out.append(self._fragment(block, filetype))
            else:
                out.append("".join(
                    self._fragment(p, filetype)
                    for p in split_budget(block, self.max_chars)
                ))
            i = j
        result = "".join(out)
        if text.endswith("\n") and not result.endswith("\n"):
            result += "\n"
        elif not text.endswith("\n") and result.endswith("\n"):
            result = result.rstrip("\n")
        return result, blocks


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

class State:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self._dirty = 0
        self.data: dict = {"version": 1, "files": {}}
        if path.exists():
            try:
                self.data = json.loads(path.read_text("utf-8"))
                self.data.setdefault("files", {})
            except (OSError, json.JSONDecodeError):
                pass

    def result_hash(self, rel: str) -> Optional[str]:
        entry = self.data["files"].get(rel)
        return entry.get("result_sha") if entry else None

    def record(self, rel: str, **fields) -> None:
        with self.lock:
            self.data["files"][rel] = {"ts": int(time.time()), **fields}
            self._dirty += 1
            if self._dirty >= 8:
                self._flush_locked()

    def flush(self) -> None:
        with self.lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        self._dirty = 0
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), "utf-8")
        tmp.replace(self.path)


# --------------------------------------------------------------------------- #
# File discovery
# --------------------------------------------------------------------------- #

def git_files(root: Path) -> Optional[list[Path]]:
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return [root / n.decode("utf-8") for n in res.stdout.split(b"\x00") if n]


def walk_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for f in filenames:
            out.append(Path(dirpath) / f)
    return out


def is_candidate(path: Path, self_path: Path, state_path: Path) -> bool:
    if not path.is_file():
        return False
    if path in (self_path, state_path):
        return False
    name = path.name
    if name in SKIP_NAMES or is_secret_file(name):
        return False
    if path.suffix.lower() in SKIP_EXTS or name.endswith((".min.js", ".min.css")):
        return False
    if any(part in SKIP_DIRS or part.startswith(".venv") for part in path.parts):
        return False
    return True


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def build_client(args) -> OpenAI:
    api_key = (
        args.api_key
        or os.environ.get("TRANSLATE_API_KEY")
        or os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        sys.exit(
            "No API key found. Set DEEPSEEK_API_KEY (or TRANSLATE_API_KEY / "
            "OPENAI_API_KEY) in the environment, or pass --api-key."
        )
    base_url = (
        args.base_url
        or os.environ.get("TRANSLATE_BASE_URL")
        or os.environ.get("DEEPSEEK_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.deepseek.com"
    )
    return OpenAI(api_key=api_key, base_url=base_url, timeout=180.0, max_retries=0)


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="Translate Chinese text in the repo to English, in place.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent,
                   help="Repository root to translate.")
    p.add_argument("--model", default=os.environ.get("TRANSLATE_MODEL")
                   or os.environ.get("DEEPSEEK_MODEL")
                   or os.environ.get("OPENAI_MODEL") or "deepseek-chat",
                   help="Chat model name.")
    p.add_argument("--base-url", default=None, help="OpenAI-compatible base URL.")
    p.add_argument("--api-key", default=None,
                   help="API key (prefer the environment variable instead).")
    p.add_argument("--workers", type=int, default=6, help="Parallel API workers.")
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--max-chars", type=int, default=6000,
                   help="Max characters per API request before splitting.")
    p.add_argument("--max-output-tokens", type=int, default=8192)
    p.add_argument("--max-file-bytes", type=int, default=2_000_000,
                   help="Skip files larger than this.")
    p.add_argument("--include", action="append", default=[],
                   help="Only translate paths matching this glob (repeatable).")
    p.add_argument("--exclude", action="append", default=[],
                   help="Skip paths matching this glob (repeatable).")
    p.add_argument("--limit", type=int, default=0, help="Translate at most N files.")
    p.add_argument("--all-files", action="store_true",
                   help="Walk the filesystem instead of using 'git ls-files'.")
    p.add_argument("--force", action="store_true",
                   help="Re-translate even files already recorded as done.")
    p.add_argument("--cleanup", action="store_true",
                   help="Surgical mode: re-translate only the lines that still "
                        "contain Chinese (implies reprocessing candidates).")
    p.add_argument("--state-file", type=Path, default=None,
                   help="Path to the resume-state JSON file.")
    p.add_argument("--list", action="store_true",
                   help="List candidate files and exit (no API calls).")
    p.add_argument("--dry-run", action="store_true",
                   help="Alias for --list.")
    return p.parse_args(argv)


def collect_candidates(args, self_path: Path, state_path: Path):
    root: Path = args.root.resolve()
    raw = None if args.all_files else git_files(root)
    if raw is None:
        raw = walk_files(root)
    candidates = []
    for path in raw:
        path = path.resolve()
        if not is_candidate(path, self_path, state_path):
            continue
        rel = os.path.relpath(path, root)
        if args.include and not match_globs(rel, args.include):
            continue
        if args.exclude and match_globs(rel, args.exclude):
            continue
        try:
            if path.stat().st_size > args.max_file_bytes:
                continue
        except OSError:
            continue
        text = read_text(path)
        if text is None or not has_chinese(text):
            continue
        candidates.append((path, rel, text))
    return root, candidates


def main(argv=None) -> int:
    args = parse_args(argv)
    self_path = Path(__file__).resolve()
    root = args.root.resolve()
    state_path = (args.state_file or (root / ".translate_state.json")).resolve()

    print(f"Scanning {root} ...", flush=True)
    root, candidates = collect_candidates(args, self_path, state_path)

    state = State(state_path)
    if not args.force and not args.cleanup:
        pending = []
        for path, rel, text in candidates:
            if state.result_hash(rel) == sha256(text):
                continue  # already translated by us and unchanged
            pending.append((path, rel, text))
    else:
        pending = candidates

    total_bytes = sum(len(t.encode("utf-8")) for _, _, t in pending)
    print(f"Candidates with Chinese text: {len(candidates)}")
    print(f"Pending (not yet done):       {len(pending)}  "
          f"(~{total_bytes/1_000_000:.2f} MB of text)")

    if args.limit:
        pending = pending[: args.limit]
        print(f"Limited to first {len(pending)} file(s).")

    if args.list or args.dry_run:
        for _, rel, text in pending:
            print(f"  {rel}  ({len(text)} chars)")
        print(f"\n[list] {len(pending)} file(s) would be translated. No API calls made.")
        return 0

    if not pending:
        print("Nothing to do - everything is already translated.")
        return 0

    client = build_client(args)
    translator = Translator(
        client=client, model=args.model, temperature=args.temperature,
        max_output_tokens=args.max_output_tokens, max_chars=args.max_chars,
    )
    print(f"Model: {args.model}   Workers: {args.workers}\n")

    counter = {"done": 0, "changed": 0, "failed": 0}
    clock = threading.Lock()
    n = len(pending)

    def work(item):
        path, rel, text = item
        t0 = time.time()
        try:
            if args.cleanup:
                new_text, chunks = translator.cleanup(text, type_hint(path))
            else:
                new_text, chunks = translator.translate(text, type_hint(path))
        except Exception as exc:  # noqa: BLE001
            state.record(rel, status="error", error=str(exc)[:300])
            with clock:
                counter["failed"] += 1
                i = counter["done"] + counter["failed"]
                print(f"[{i:>4}/{n}] FAIL {rel}\n         {exc}", flush=True)
            return
        changed = new_text != text
        if changed:
            path.write_text(new_text, "utf-8")
        state.record(rel, status="done", changed=changed,
                     source_sha=sha256(text), result_sha=sha256(new_text))
        with clock:
            counter["done"] += 1
            if changed:
                counter["changed"] += 1
            i = counter["done"] + counter["failed"]
            flag = "OK " if changed else "== "  # '==' => model returned unchanged
            print(f"[{i:>4}/{n}] {flag}{rel}  "
                  f"(chunks={chunks}, {time.time()-t0:.1f}s)", flush=True)

    try:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(work, pending))
    except KeyboardInterrupt:
        print("\nInterrupted - progress saved to state file; re-run to resume.")
    finally:
        state.flush()

    print(f"\nDone. translated={counter['changed']} "
          f"unchanged={counter['done'] - counter['changed']} "
          f"failed={counter['failed']}  state={state_path.name}")
    return 1 if counter["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
