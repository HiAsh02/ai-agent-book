#!/usr/bin/env python3
"""Translate Chinese file and directory names to English (in place, via git mv).

Only path *names* are changed - file contents are untouched. Each Chinese path
component is translated to English through an OpenAI-compatible model and then
slugified into a safe filename (ASCII, lowercase, underscores). Identical
components map to the same slug, so a renamed directory stays consistent across
all the files inside it. Collisions within a directory get a numeric suffix.

    export DEEPSEEK_API_KEY=sk-...
    python translate_filenames.py --dry-run     # preview every rename
    python translate_filenames.py               # perform the git mv renames
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    sys.exit("The 'openai' package is required. Install with: pip install openai")

CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\U00020000-\U0002a6df]")

# Files whose target name is fixed (must match references elsewhere in the repo).
FIXED_RENAMES = {
    "book/深入理解-AI-Agent-李博杰-v1.1.pdf":
        "book/Deep-Understanding-of-AI-Agents-Li-Bojie-v1.1.pdf",
}

SYSTEM = """\
You translate Chinese file/directory name fragments into concise English.
Return a JSON object {"translations": [...]} whose array has EXACTLY the same
length and order as the input array. For each fragment:
- Translate the Chinese into short, clear English (a few words; keep it concise).
- Keep any existing English words, numbers, and dates (e.g. 1998-06-26) as-is.
- Do NOT add file extensions, quotes, slashes, or explanations.
Example: "2-宪法相关法" -> "2 Constitution-related Laws";
"专属经济区和大陆架法（1998-06-26）" -> "Exclusive Economic Zone and Continental Shelf Law (1998-06-26)"."""


def has_chinese(s: str) -> bool:
    return CJK_RE.search(s) is not None


def slugify(text: str, max_len: int = 90) -> str:
    """Turn translated English text into a safe, lowercase filename slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")  # drop any residue
    text = text.replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"[_-]{2,}", lambda m: m.group(0)[0], text)
    text = text.strip("._-").lower()
    if len(text) > max_len:
        text = text[:max_len].rstrip("._-")
    return text or "untitled"


class Translator:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    def _chat(self, payload: str) -> str:
        last = None
        for attempt in range(5):
            try:
                r = self.client.chat.completions.create(
                    model=self.model, temperature=0.2,
                    response_format={"type": "json_object"},
                    messages=[{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": payload}])
                c = r.choices[0].message.content or ""
                if c.strip():
                    return c
                raise RuntimeError("empty")
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(min(2 ** attempt, 20))
        raise RuntimeError(f"API failed: {last}")

    def translate_many(self, items: list[str], batch: int = 40) -> dict[str, str]:
        uniq = [s for s in dict.fromkeys(items) if has_chinese(s)]
        out: dict[str, str] = {}
        for i in range(0, len(uniq), batch):
            chunk = uniq[i:i + batch]
            raw = self._chat(json.dumps({"fragments": chunk}, ensure_ascii=False))
            trans = None
            try:
                arr = json.loads(raw).get("translations")
                if isinstance(arr, list) and len(arr) == len(chunk):
                    trans = [str(x) for x in arr]
            except (json.JSONDecodeError, AttributeError, TypeError):
                trans = None
            if trans is None:  # one-by-one fallback
                trans = []
                for s in chunk:
                    r1 = self._chat(json.dumps({"fragments": [s]}, ensure_ascii=False))
                    try:
                        a = json.loads(r1)["translations"]
                        trans.append(str(a[0]) if a else s)
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        trans.append(s)
            for src, dst in zip(chunk, trans):
                out[src] = dst
            print(f"  translated {min(i + batch, len(uniq))}/{len(uniq)} name fragments",
                  flush=True)
        return out


def git_paths(root: Path) -> list[str]:
    res = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(root),
                          "ls-files"], stdout=subprocess.PIPE, text=True, check=True)
    return [ln for ln in res.stdout.splitlines() if ln]


def split_stem_ext(name: str) -> tuple[str, str]:
    # treat only the final extension of known text/media kinds as an extension
    m = re.search(r"(\.[A-Za-z0-9]{1,8})$", name)
    if m:
        return name[: m.start()], m.group(1)
    return name, ""


def build_client(args) -> OpenAI:
    key = (args.api_key or os.environ.get("TRANSLATE_API_KEY")
           or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    if not key:
        sys.exit("No API key. Set DEEPSEEK_API_KEY (or pass --api-key).")
    base = (args.base_url or os.environ.get("TRANSLATE_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
            or "https://api.deepseek.com")
    return OpenAI(api_key=key, base_url=base, timeout=120.0, max_retries=0)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--model", default=os.environ.get("TRANSLATE_MODEL")
                   or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat")
    p.add_argument("--base-url", default=None)
    p.add_argument("--api-key", default=None)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    root = args.root.resolve()

    paths = [p for p in git_paths(root) if has_chinese(p)]
    if args.limit:
        paths = paths[: args.limit]
    print(f"Paths with Chinese in their name: {len(paths)}")
    if not paths:
        return 0

    # Collect the translatable name fragments (dir names + file stems).
    fragments: list[str] = []
    for rel in paths:
        if rel in FIXED_RENAMES:
            continue
        parts = rel.split("/")
        for idx, part in enumerate(parts):
            if not has_chinese(part):
                continue
            if idx == len(parts) - 1:
                stem, _ = split_stem_ext(part)
                fragments.append(stem)
            else:
                fragments.append(part)

    mapping: dict[str, str] = {}
    if fragments:
        client = build_client(args)
        mapping = Translator(client, args.model).translate_many(fragments)

    # Compute new relative paths.
    renames: list[tuple[str, str]] = []
    used: dict[str, int] = {}
    for rel in paths:
        if rel in FIXED_RENAMES:
            renames.append((rel, FIXED_RENAMES[rel]))
            continue
        parts = rel.split("/")
        new_parts = []
        for idx, part in enumerate(parts):
            if not has_chinese(part):
                new_parts.append(part)
                continue
            if idx == len(parts) - 1:
                stem, ext = split_stem_ext(part)
                slug = slugify(mapping.get(stem, stem))
                new_parts.append(slug + ext.lower())
            else:
                new_parts.append(slugify(mapping.get(part, part)))
        new_rel = "/".join(new_parts)
        # de-duplicate collisions within the same target directory
        base = new_rel
        while new_rel in used or (new_rel != rel and (root / new_rel).exists()
                                  and new_rel not in [r[1] for r in renames]):
            used[base] = used.get(base, 1) + 1
            stem, ext = split_stem_ext(base)
            new_rel = f"{stem}_{used[base]}{ext}"
        used[new_rel] = 1
        if new_rel != rel:
            renames.append((rel, new_rel))

    print(f"\nRenames to perform: {len(renames)}")
    for old, new in renames[:12]:
        print(f"  {old}\n   -> {new}")
    if len(renames) > 12:
        print(f"  ... and {len(renames) - 12} more")

    if args.dry_run:
        print("\n[dry-run] no files changed.")
        return 0

    ok = 0
    for old, new in renames:
        (root / new).parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "-C", str(root), "mv", old, new],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  FAIL {old} -> {new}: {r.stderr.strip()}", flush=True)
        else:
            ok += 1
    print(f"\nDone. renamed {ok}/{len(renames)} paths.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
