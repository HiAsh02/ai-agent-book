#!/usr/bin/env python3
"""Syntax-safe Chinese->English translator for source code and data files.

Unlike a whole-file translation (which corrupts code), this tool only ever
rewrites the *content* of comments and string literals, leaving every bit of
program structure - identifiers, operators, delimiters, brackets, placeholders -
byte-for-byte intact. Syntax validity is guaranteed by construction:

* Python (.py)         - the standard ``tokenize`` module locates COMMENT,
  STRING and FSTRING_MIDDLE tokens; only their text is translated and the
  original quotes/prefixes are kept (delimiters are re-escaped in the output).
  f-string ``{expr}`` parts are separate tokens and are never touched.
* JSON / JSONL         - parsed, string *values* translated, keys kept, re-dumped.
* C-like & others      - a small scanner finds line/block comments and string
  literals for JS/TS/TSX/JSX/Lua/SQL/CSS/LESS/Shell/LaTeX/YAML/TOML. Template
  literals are split on ``${...}`` so interpolated code is preserved.

Only segments that actually contain Chinese are sent to the model; identical
segments are de-duplicated and translated in batches.

    export DEEPSEEK_API_KEY=sk-...
    python translate_code_safe.py --list
    python translate_code_safe.py --lang py --limit 5
    python translate_code_safe.py            # all supported code/data files
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import token as token_mod
import tokenize
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, Optional
from xml.sax.saxutils import escape as xml_escape, unescape as xml_unescape

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    sys.exit("The 'openai' package is required. Install with: pip install openai")

CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002a6df]")

# Backslashes are protected with this ASCII sentinel while crossing the JSON
# transport, otherwise json.loads would decode the model's escape sequences
# (e.g. turn a source `\n` into a real newline and break the literal). An ASCII
# token is used because models reliably preserve it verbatim (a private-use
# character can be normalised into a null byte by some providers).
BS_SENTINEL = "\u27e6BSLASH\u27e7"


def has_chinese(text: str) -> bool:
    return CJK_RE.search(text) is not None


# --------------------------------------------------------------------------- #
# Batched segment translator
# --------------------------------------------------------------------------- #

SEG_SYSTEM = """\
You are a translation engine embedded in a source-code localization pipeline.
You receive a JSON array of text SEGMENTS extracted from code comments and string
literals. Translate each segment from Chinese to fluent, idiomatic technical
English.

Absolute rules:
- Translate ONLY Chinese text. Keep English, numbers and identifiers unchanged.
- PRESERVE every placeholder and escape EXACTLY, character for character:
  {name} {0} {} {{ }} ${expr} %s %d %(x)s \\n \\t \\r \\\\ \\" \\' , HTML tags,
  Markdown, URLs, file paths, and format specifiers.
- PRESERVE leading and trailing whitespace of each segment.
- Do NOT add or remove surrounding quotes. Do NOT add explanations.
- The marker token \u27e6BSLASH\u27e7 may appear inside segments; keep every
  occurrence of it exactly as-is (it stands in for a backslash).
- A segment that is already English or has no Chinese must be returned verbatim.

Terminology: 智能体/代理->agent, 上下文->context, 提示词->prompt, 大模型/大语言模型->LLM,
工具调用->tool call, 检索->retrieval, 记忆->memory, 模型->model, 推理->inference/reasoning.

Output a JSON object of the form {"translations": [...]} whose array has EXACTLY
the same length and order as the input array."""


class SegTranslator:
    def __init__(self, client: OpenAI, model: str, temperature: float = 0.2,
                 batch_chars: int = 4000, batch_items: int = 30, retries: int = 5):
        self.client = client
        self.model = model
        self.temperature = temperature
        self.batch_chars = batch_chars
        self.batch_items = batch_items
        self.retries = retries

    def _chat(self, payload: str) -> str:
        last = None
        for attempt in range(self.retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SEG_SYSTEM},
                        {"role": "user", "content": payload},
                    ],
                )
                content = resp.choices[0].message.content or ""
                if content.strip():
                    return content
                raise RuntimeError("empty response")
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(f"segment API failed: {last}")

    def _translate_batch(self, segs: list[str]) -> list[str]:
        prot = [s.replace("\\", BS_SENTINEL) for s in segs]
        payload = json.dumps({"segments": prot}, ensure_ascii=False)
        raw = self._chat(payload)
        try:
            obj = json.loads(raw)
            out = obj["translations"]
            if isinstance(out, list) and len(out) == len(segs):
                return [str(x).replace(BS_SENTINEL, "\\") for x in out]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        # fall back to one-by-one so a bad batch cannot corrupt alignment
        result = []
        for s in segs:
            p = s.replace("\\", BS_SENTINEL)
            raw1 = self._chat(json.dumps({"segments": [p]}, ensure_ascii=False))
            try:
                o = json.loads(raw1)["translations"]
                result.append(str(o[0]).replace(BS_SENTINEL, "\\")
                              if isinstance(o, list) and o else s)
            except (json.JSONDecodeError, KeyError, TypeError, IndexError):
                result.append(s)
        return result

    def translate_many(self, texts: list[str]) -> list[str]:
        """Translate a list of texts, preserving order. Only Chinese ones are sent."""
        uniq = [t for t in dict.fromkeys(texts) if has_chinese(t)]
        mapping: dict[str, str] = {}
        batch: list[str] = []
        size = 0
        for t in uniq:
            if batch and (size + len(t) > self.batch_chars or len(batch) >= self.batch_items):
                for src, dst in zip(batch, self._translate_batch(batch)):
                    mapping[src] = dst
                batch, size = [], 0
            batch.append(t)
            size += len(t)
        if batch:
            for src, dst in zip(batch, self._translate_batch(batch)):
                mapping[src] = dst
        return [mapping.get(t, t) for t in texts]


# --------------------------------------------------------------------------- #
# Delimiter escaping
# --------------------------------------------------------------------------- #

def escape_delim(body: str, quote: str) -> str:
    """Escape occurrences of a single-char quote in ``body`` (respecting existing
    escapes). For triple quotes we only fix a dangling closing sequence."""
    if len(quote) == 1:
        out = []
        i, n = 0, len(body)
        while i < n:
            c = body[i]
            if c == "\\" and i + 1 < n:
                out.append(body[i:i + 2])
                i += 2
                continue
            if c == quote:
                out.append("\\" + quote)
                i += 1
                continue
            out.append(c)
            i += 1
        body = "".join(out)
    elif body.endswith(quote[0]):
        # e.g. body ends with a quote char that would merge with the closing """
        body += " "
    # guard against a trailing odd backslash escaping the closing quote (all kinds)
    trail = len(body) - len(body.rstrip("\\"))
    if trail % 2 == 1:
        body += "\\"
    return body


def enc_body(body: str, quote: str, multiline: bool) -> str:
    """Encode a translated string body: escape the delimiter and, for single-line
    strings, turn any real control characters (which the JSON transport may have
    produced from ``\\n`` etc.) back into escape sequences so the literal stays
    on one line and valid."""
    body = escape_delim(body, quote)
    if not multiline:
        body = (body.replace("\r\n", "\\n").replace("\n", "\\n")
                    .replace("\r", "\\r").replace("\t", "\\t"))
    return body


# --------------------------------------------------------------------------- #
# Python handler (tokenize)
# --------------------------------------------------------------------------- #

def _line_offsets(src: str) -> list[int]:
    offs, pos = [0], 0
    for line in src.splitlines(keepends=True):
        pos += len(line)
        offs.append(pos)
    return offs


def _split_py_string(tokstr: str):
    m = re.match(r"^([A-Za-z]*)(\"\"\"|'''|\"|')", tokstr)
    if not m:
        return None
    prefix, quote = m.group(1), m.group(2)
    body = tokstr[len(prefix) + len(quote): len(tokstr) - len(quote)]
    return prefix, quote, body


def collect_python(src: str) -> list[tuple[int, int, str, Callable[[str], str]]]:
    """Return (start, end, current_text, rebuild) spans for translatable content."""
    offs = _line_offsets(src)

    def to_off(pos):
        r, c = pos
        return offs[r - 1] + c

    spans: list[tuple[int, int, str, Callable[[str], str]]] = []
    fstring_delims: list[str] = []
    FSTART = getattr(token_mod, "FSTRING_START", -1)
    FMID = getattr(token_mod, "FSTRING_MIDDLE", -1)
    FEND = getattr(token_mod, "FSTRING_END", -1)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []
    for tok in toks:
        s, e = to_off(tok.start), to_off(tok.end)
        if tok.type == token_mod.COMMENT:
            content = tok.string[1:]  # after '#'
            if content.startswith("!") and tok.start[0] == 1:
                continue  # shebang
            if not has_chinese(content):
                continue
            spans.append((s + 1, e, content,
                          lambda t: t.replace("\n", " ").replace("\r", " ")))
        elif tok.type == FSTART:
            m = re.match(r"^[A-Za-z]*(\"\"\"|'''|\"|')", tok.string)
            fstring_delims.append(m.group(1) if m else '"')
        elif tok.type == FEND:
            if fstring_delims:
                fstring_delims.pop()
        elif tok.type == FMID:
            if not has_chinese(tok.string):
                continue
            q = fstring_delims[-1] if fstring_delims else '"'
            spans.append((s, e, tok.string,
                          lambda t, q=q: enc_body(t, q, len(q) > 1)))
        elif tok.type == token_mod.STRING:
            parts = _split_py_string(tok.string)
            if not parts:
                continue
            prefix, quote, body = parts
            low = prefix.lower()
            if "b" in low:
                continue  # bytes
            if not has_chinese(body):
                continue
            raw = "r" in low
            inner_start = s + len(prefix) + len(quote)
            inner_end = e - len(quote)
            if raw:
                # cannot escape in raw strings; skip if the translation would
                # introduce the delimiter or (for single-line) a newline
                spans.append((inner_start, inner_end, body,
                              lambda t, q=quote: t if (q not in t and (len(q) > 1 or "\n" not in t)) else None))
            else:
                spans.append((inner_start, inner_end, body,
                              lambda t, q=quote: enc_body(t, q, len(q) > 1)))
    return spans


# --------------------------------------------------------------------------- #
# Generic scanner for C-like and other languages
# --------------------------------------------------------------------------- #

LANG_CFG = {
    "js":   dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template="`"),
    "mjs":  dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template="`"),
    "cjs":  dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template="`"),
    "ts":   dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template="`"),
    "tsx":  dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template="`"),
    "jsx":  dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template="`"),
    "lua":  dict(line=["--"], block=[("--[[", "]]")], quotes=['"', "'"], template=None),
    "sql":  dict(line=["--"], block=[("/*", "*/")], quotes=["'"], template=None),
    "css":  dict(line=[], block=[("/*", "*/")], quotes=['"', "'"], template=None),
    "less": dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template=None),
    "scss": dict(line=["//"], block=[("/*", "*/")], quotes=['"', "'"], template=None),
    "sh":   dict(line=["#"], block=[], quotes=['"', "'"], template=None),
    "bash": dict(line=["#"], block=[], quotes=['"', "'"], template=None),
    "tex":  dict(line=["%"], block=[], quotes=[], template=None),
    "yaml": dict(line=["#"], block=[], quotes=['"', "'"], template=None),
    "yml":  dict(line=["#"], block=[], quotes=['"', "'"], template=None),
    "toml": dict(line=["#"], block=[], quotes=['"', "'"], template=None),
}


def collect_generic(src: str, cfg: dict):
    spans: list[tuple[int, int, str, Callable[[str], str]]] = []
    n = len(src)
    i = 0
    line_markers = sorted(cfg["line"], key=len, reverse=True)
    block_markers = cfg["block"]
    quotes = cfg["quotes"]
    template = cfg["template"]

    def add_comment(cs, ce):
        content = src[cs:ce]
        if has_chinese(content):
            spans.append((cs, ce, content,
                          lambda t: t.replace("\n", " ").replace("\r", " ")))

    while i < n:
        c = src[i]
        matched = False
        # block comments
        for open_m, close_m in block_markers:
            if src.startswith(open_m, i):
                j = src.find(close_m, i + len(open_m))
                if j == -1:
                    j = n
                    end = n
                else:
                    end = j
                content = src[i + len(open_m):end]
                if has_chinese(content):
                    spans.append((i + len(open_m), end, content, lambda t: t))
                i = (j + len(close_m)) if j != n else n
                matched = True
                break
        if matched:
            continue
        # line comments
        for m in line_markers:
            if src.startswith(m, i):
                j = src.find("\n", i)
                if j == -1:
                    j = n
                add_comment(i + len(m), j)
                i = j
                matched = True
                break
        if matched:
            continue
        # template literals (with ${...})
        if template and c == template:
            i += 1
            seg_start = i
            depth = 0
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if src.startswith("${", i):
                    if src[seg_start:i] and has_chinese(src[seg_start:i]):
                        spans.append((seg_start, i, src[seg_start:i],
                                      lambda t: enc_body(t, "`", True)))
                    i += 2
                    depth = 1
                    while i < n and depth:
                        if src[i] == "{":
                            depth += 1
                        elif src[i] == "}":
                            depth -= 1
                        i += 1
                    seg_start = i
                    continue
                if src[i] == template:
                    break
                i += 1
            if src[seg_start:i] and has_chinese(src[seg_start:i]):
                spans.append((seg_start, i, src[seg_start:i],
                              lambda t: enc_body(t, "`", True)))
            i += 1
            continue
        # normal strings
        if c in quotes:
            q = c
            i += 1
            body_start = i
            while i < n:
                if src[i] == "\\" and i + 1 < n:
                    i += 2
                    continue
                if src[i] == q or src[i] == "\n":
                    break
                i += 1
            body = src[body_start:i]
            if has_chinese(body):
                spans.append((body_start, i, body, lambda t, q=q: enc_body(t, q, False)))
            if i < n and src[i] == q:
                i += 1
            continue
        i += 1
    return spans


# --------------------------------------------------------------------------- #
# JSON handler
# --------------------------------------------------------------------------- #

def translate_json_obj(obj, seg: SegTranslator):
    """Translate string values (not keys) in a parsed JSON structure."""
    strings: list[str] = []

    def gather(node):
        if isinstance(node, str):
            if has_chinese(node):
                strings.append(node)
        elif isinstance(node, list):
            for x in node:
                gather(x)
        elif isinstance(node, dict):
            for v in node.values():
                gather(v)

    gather(obj)
    if not strings:
        return obj, False
    uniq = list(dict.fromkeys(strings))
    mapping = dict(zip(uniq, seg.translate_many(uniq)))

    def rebuild(node):
        if isinstance(node, str):
            return mapping.get(node, node)
        if isinstance(node, list):
            return [rebuild(x) for x in node]
        if isinstance(node, dict):
            return {k: rebuild(v) for k, v in node.items()}
        return node

    return rebuild(obj), True


# --------------------------------------------------------------------------- #
# Per-file processing
# --------------------------------------------------------------------------- #

def apply_spans(src: str, spans, translations) -> str:
    """Apply (start,end,_,rebuild) spans with matching translations, back to front."""
    items = []
    for (start, end, _orig, rebuild), new in zip(spans, translations):
        built = rebuild(new)
        if built is None:  # rebuild vetoed the change (e.g. raw string)
            continue
        items.append((start, end, built))
    for start, end, built in sorted(items, key=lambda x: x[0], reverse=True):
        src = src[:start] + built + src[end:]
    return src


def process_file(path: Path, seg: SegTranslator) -> tuple[bool, str]:
    ext = path.suffix.lower().lstrip(".")
    text = path.read_text("utf-8")
    if ext in ("svg", "xml"):
        # translate only text-node content (between tags); escape result so the
        # document stays well-formed. Attributes/structure are left untouched.
        matches = [(m.start(1), m.end(1), m.group(1))
                   for m in re.finditer(r">([^<>]*)<", text)
                   if has_chinese(m.group(1))]
        if not matches:
            return False, "no-chinese"
        trans = seg.translate_many([xml_unescape(m[2]) for m in matches])
        new_text = text
        for (s, e, _o), tr in sorted(zip(matches, trans), key=lambda x: x[0][0],
                                     reverse=True):
            new_text = new_text[:s] + xml_escape(tr) + new_text[e:]
    elif ext in ("json",):
        obj = json.loads(text)
        new_obj, changed = translate_json_obj(obj, seg)
        if not changed:
            return False, "no-chinese"
        indent = 2 if text.lstrip().startswith(("{", "[")) and "\n" in text else None
        new_text = json.dumps(new_obj, ensure_ascii=False,
                              indent=2 if "\n  " in text or "\n    " in text else None)
        if not text.endswith("\n"):
            new_text = new_text.rstrip("\n")
        elif not new_text.endswith("\n"):
            new_text += "\n"
    elif ext in ("jsonl", "ndjson"):
        out_lines = []
        for line in text.splitlines(keepends=True):
            stripped = line.strip()
            if stripped and has_chinese(line):
                nl = "\n" if line.endswith("\n") else ""
                obj = json.loads(stripped)
                new_obj, _ = translate_json_obj(obj, seg)
                out_lines.append(json.dumps(new_obj, ensure_ascii=False) + nl)
            else:
                out_lines.append(line)
        new_text = "".join(out_lines)
    else:
        if ext == "py":
            spans = collect_python(text)
        elif ext in LANG_CFG:
            spans = collect_generic(text, LANG_CFG[ext])
        else:
            return False, "unsupported"
        if not spans:
            return False, "no-chinese"
        translations = seg.translate_many([s[2] for s in spans])
        new_text = apply_spans(text, spans, translations)
    if new_text == text:
        return False, "unchanged"
    err = validate_text(new_text, ext)
    if err:
        return False, f"invalid: {err}"  # never write a broken file
    path.write_text(new_text, "utf-8")
    return True, "ok"


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #

def validate_text(text: str, ext: str) -> Optional[str]:
    """Validate translated content BEFORE writing. Returns an error string or None."""
    if "\x00" in text:
        return "contains null byte"
    try:
        if ext == "py":
            import ast
            ast.parse(text)
        elif ext in ("svg", "xml"):
            ET.fromstring(text)
        elif ext == "json":
            json.loads(text)
        elif ext in ("jsonl", "ndjson"):
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
        elif ext in ("js", "mjs", "cjs"):
            import tempfile
            with tempfile.NamedTemporaryFile("w", suffix="." + ext, delete=False,
                                             encoding="utf-8") as tf:
                tf.write(text)
                tmp = tf.name
            try:
                r = subprocess.run(["node", "--check", tmp],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    lines = (r.stderr or "").strip().splitlines()
                    return lines[-1] if lines else "node --check failed"
            finally:
                os.unlink(tmp)
    except Exception as exc:  # noqa: BLE001
        return str(exc)[:200]
    return None


# --------------------------------------------------------------------------- #
# Discovery & main
# --------------------------------------------------------------------------- #

SUPPORTED = {"py", "json", "jsonl", "ndjson", "svg", "xml", *LANG_CFG.keys()}


def git_files(root: Path) -> list[Path]:
    res = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                         stdout=subprocess.PIPE)
    return [root / n.decode("utf-8") for n in res.stdout.split(b"\x00") if n]


def build_client(args) -> OpenAI:
    key = (args.api_key or os.environ.get("TRANSLATE_API_KEY")
           or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if not key:
        sys.exit("No API key. Set DEEPSEEK_API_KEY (or pass --api-key).")
    base = (args.base_url or os.environ.get("TRANSLATE_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
            or "https://api.deepseek.com")
    return OpenAI(api_key=key, base_url=base, timeout=180.0, max_retries=0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--model", default=os.environ.get("TRANSLATE_MODEL")
                   or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat")
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--lang", default="all",
                   help="Comma list of extensions to process (e.g. py,json) or 'all'.")
    p.add_argument("--include", action="append", default=[])
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--list", action="store_true")
    args = p.parse_args(argv)

    root = args.root.resolve()
    self_path = Path(__file__).resolve()
    langs = SUPPORTED if args.lang == "all" else set(args.lang.split(","))

    import fnmatch
    candidates = []
    for path in git_files(root):
        path = path.resolve()
        if path == self_path or not path.is_file():
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext not in langs or ext not in SUPPORTED:
            continue
        rel = os.path.relpath(path, root)
        if args.include and not any(fnmatch.fnmatch(rel, g) for g in args.include):
            continue
        if args.exclude and any(fnmatch.fnmatch(rel, g) for g in args.exclude):
            continue
        try:
            text = path.read_text("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if has_chinese(text):
            candidates.append((path, rel))

    print(f"Supported files with Chinese: {len(candidates)}")
    if args.limit:
        candidates = candidates[: args.limit]
    if args.list:
        for _, rel in candidates:
            print(f"  {rel}")
        print(f"[list] {len(candidates)} file(s). No API calls.")
        return 0
    if not candidates:
        print("Nothing to do.")
        return 0

    client = build_client(args)
    seg = SegTranslator(client, args.model, temperature=args.temperature)
    print(f"Model: {args.model}  Workers: {args.workers}\n")

    counters = {"changed": 0, "skipped": 0, "failed": 0, "invalid": 0}
    lock = threading.Lock()
    n = len(candidates)

    def work(item):
        path, rel = item
        t0 = time.time()
        try:
            changed, status = process_file(path, seg)
        except Exception as exc:  # noqa: BLE001
            with lock:
                counters["failed"] += 1
                done = sum(counters.values())
                print(f"[{done:>4}/{n}] FAIL {rel}: {str(exc)[:150]}", flush=True)
            return
        with lock:
            done = sum(counters.values()) + 1
            if status.startswith("invalid"):
                counters["invalid"] += 1
                print(f"[{done:>4}/{n}] INVALID {rel}: {status} (left unchanged)", flush=True)
            elif changed:
                counters["changed"] += 1
                print(f"[{done:>4}/{n}] OK   {rel} ({time.time()-t0:.1f}s)", flush=True)
            else:
                counters["skipped"] += 1
                print(f"[{done:>4}/{n}] --   {rel} ({status})", flush=True)

    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, candidates))

    print(f"\nDone. changed={counters['changed']} skipped={counters['skipped']} "
          f"failed={counters['failed']} invalid={counters['invalid']}")
    return 1 if (counters["failed"] or counters["invalid"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
