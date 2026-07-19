"""
Experiment 10-3: Book Translation Agent — Orchestration Mode

This module implements four specialized agents and two operation modes:
  1) Orchestration mode: Manager only stores tasks/plans/call records/file indices,
     without saving complete translations; each sub-agent has independent, isolated context.
  2) Single-agent mode: One agent reads the entire book and translates chapter by chapter
     in a continuously growing conversation, used to compare "context bloat" and "term drift".

Core verification points:
  - Record the context token consumption of each agent/manager;
  - Prove that in orchestration mode, the manager's context is significantly smaller than the cumulative context of a single agent;
  - Prove that a shared glossary ensures term consistency across chapters.
"""

import os
import json

import tiktoken
from openai import OpenAI


# ----------------------------------------------------------------------------
#  Configuration: model / base_url can be overridden via environment variables, default current cheap flagship gpt-5.6-luna
# ----------------------------------------------------------------------------
MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
BASE_URL = os.environ.get("OPENAI_BASE_URL")  #  Optional, compatible with self-hosted/proxy endpoints


def _to_openrouter_model(model: str) -> str:
    """Map model names to OpenRouter namespace (for fallback path without OPENAI_API_KEY)."""
    if "/" in model:
        return model                      #  Already OpenRouter namespace, use as-is
    if model.startswith("gpt-"):
        return "openai/" + model          # gpt-* -> openai/gpt-*
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"          #  Fallback: current cheap flagship


def get_client() -> OpenAI:
    """Create an LLM client.

    General fallback strategy:
      1) If OPENAI_API_KEY is set -> connect directly to OpenAI (respect optional OPENAI_BASE_URL);
      2) Otherwise if OPENROUTER_API_KEY is set -> automatically switch to OpenRouter gateway and map MODEL
         to OpenRouter namespace (e.g., gpt-5.6-luna -> openai/gpt-5.6-luna);
      3) If neither is set, raise a clear error.
    """
    global MODEL
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        kwargs = {"api_key": api_key}
        if BASE_URL:
            kwargs["base_url"] = BASE_URL
        return OpenAI(**kwargs)
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if or_key:
        MODEL = _to_openrouter_model(MODEL)
        return OpenAI(api_key=or_key, base_url="https://openrouter.ai/api/v1")
    raise RuntimeError(
        "Neither OPENAI_API_KEY nor OPENROUTER_API_KEY is set. Please refer to env.example for configuration."
    )


# tiktoken encoder: used to count tokens of context not actually sent to the model (e.g., manager state)
try:
    _ENC = tiktoken.encoding_for_model(MODEL)
except Exception:
    _ENC = tiktoken.get_encoding("o200k_base")


def _slug(name: str) -> str:
    """Convert chapter name to a clean file name prefix, e.g., 'Chapter 1: ...' -> 'chapter1'."""
    import re
    m = re.search(r"chapter\s*0*(\d+)", name, re.IGNORECASE)
    if m:
        return f"chapter{m.group(1)}"
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower() or "chapter"


def _loads_lenient(content: str):
    """Fault-tolerant JSON parsing: handles cases where the model wraps JSON in ```json ... ``` code fences."""
    s = (content or "").strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[-1] if "\n" in s else s
        s = s.rsplit("```", 1)[0].strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return json.loads(s)


def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    return len(_ENC.encode(text or ""))


def count_messages_tokens(messages) -> int:
    """Count the number of tokens in a set of chat messages (approximate: content + fixed overhead per message)."""
    total = 0
    for m in messages:
        total += count_tokens(m.get("content", "")) + 4  #  Each message has about 4 tokens of structural overhead
    return total


# ----------------------------------------------------------------------------
# Token tracker: records the context size of every LLM call, aggregated by agent
# ----------------------------------------------------------------------------
class TokenTracker:
    """
    Record the context token consumption of each agent per call.

    - prompt_tokens: the size of the "context" sent to the model in this call (real API usage).
      This is the key metric for measuring "context bloat".
    - peak: the maximum single-call context size for a given agent (context peak).
    """

    def __init__(self):
        self.calls = []  #  One record per call

    def record(self, agent, prompt_tokens, completion_tokens, note=""):
        self.calls.append(
            {
                "agent": agent,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "note": note,
            }
        )

    def by_agent(self):
        """Aggregate by agent: call count, total input/output, context peak."""
        agg = {}
        for c in self.calls:
            a = agg.setdefault(
                c["agent"],
                {"calls": 0, "in": 0, "out": 0, "peak_context": 0},
            )
            a["calls"] += 1
            a["in"] += c["prompt_tokens"]
            a["out"] += c["completion_tokens"]
            a["peak_context"] = max(a["peak_context"], c["prompt_tokens"])
        return agg

    def total_tokens(self):
        return sum(c["prompt_tokens"] + c["completion_tokens"] for c in self.calls)


# ----------------------------------------------------------------------------
# LLM call wrapper: each call includes the agent name for per-agent accounting
# ----------------------------------------------------------------------------
def llm_chat(client, tracker, agent, messages, json_mode=False, note=""):
    """
    Make a chat completion call and record the real token usage in the tracker.

    Note: messages is the "independent context" for this call. Sub-agents construct messages from scratch each time,
    so each agent's context is naturally isolated and does not contaminate others.
    """
    kwargs = {"model": MODEL, "messages": messages, "temperature": 0.2}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        #  Reasoning models (e.g., gpt-5.x) only accept default temperature and reject custom values;
        #  in that case, remove temperature and retry once, keeping other parameters unchanged.
        if "temperature" in str(e).lower():
            kwargs.pop("temperature", None)
            resp = client.chat.completions.create(**kwargs)
        else:
            raise
    usage = resp.usage
    tracker.record(agent, usage.prompt_tokens, usage.completion_tokens, note)
    return resp.choices[0].message.content


# ============================================================================
#  Four specialized agents
# ============================================================================

#  Editorial house style terms: the manager forces these translations into the shared glossary,
#  so all translation agents use them consistently across the book. Single agent cannot see the glossary and cannot enforce them.
EDITORIAL_MANDATE = {
    "token": "token",
    "prompt": "prompt",
    "latency": "latency",
    "embedding": "embedding vector",
}


def translation_guide(target_lang="Chinese"):
    """Generate translation guidelines in the target language. Default is Chinese, maintaining consistency with the old behavior."""
    return (
        f"Translation Guide: For{target_lang}For technical readers, the language should be fluent and natural; preserve the Markdown structure;"
        "Code inside code blocks is kept as-is and not translated (English comments may be retained);"
        "Terms appearing in the glossary must strictly use the prescribed translations; for new terms not in the glossary,"
        "First provide your inferred translation, followed immediately by the marker [待审] to prompt manual review."
    )


# Backward compatibility: Module-level default (English→Chinese) translation guide, referenced by Manager context display, etc.
TRANSLATION_GUIDE = translation_guide("Chinese")


# Fixed execution plan for Manager (shared by the actual run and the --dry-run Agent graph to avoid drift between the two).
ORCHESTRATION_PLAN = [
    "1. Call Glossary Agent to generate glossary and persist to disk",
    "2. Call Translation Agent chapter by chapter (each with independent context, sharing a terminology file)",
    "3. Call the Proofreading Agent for consistency review and save the report",
    "4. Decide whether to send back individual chapter revisions based on the report.",
]


def glossary_agent(client, tracker, book_text, source_lang="English", target_lang="Chinese"):
    """
    Glossary Agent: Read the full book content, identify recurring technical terms,
    output a structured term glossary (JSON). Independent context, can be released after output.
    """
    system = (
        f"You are a terminology extraction expert. Read the entire book{source_lang}Technical book, identify recurring technical terms."
        f"Provide a unified definition for each term{target_lang}Translation method. Output JSON only."
    )
    user = (
        "Please read the entire book below and extract 6-10 recurring core technical terms."
        "Output JSON in the format:"
        f'{{"glossary": [{{"en": "{source_lang}术语", "zh": "{target_lang}译法", '
        '"pos": "part of speech", "context": "Explanation of the term\'s context in the book"'
        "The full content is as follows:\n\n" + book_text
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = llm_chat(
        client, tracker, "Glossary", messages, json_mode=True, note="Extract glossary"
    )
    data = _loads_lenient(content)
    return data.get("glossary", [])


def translation_agent(client, tracker, chapter_text, glossary, chapter_name,
                      feedback=None, source_lang="English", target_lang="Chinese"):
    """
    Translation Agent: Receives "current chapter + glossary + translation guide" and produces fluent translation.
    Each instance has an independent context (only sees its own chapter + glossary, not other chapters' translations).

    feedback: Optional, revision suggestions for this chapter sent back by Manager based on review report.
    """
    glossary_lines = "\n".join(
        f'- {g["en"]} → {g["zh"]}（{g.get("pos","")}）' for g in glossary
    )
    system = f"You are a professional technical translator. Translate{source_lang}Translate chapters into fluent and accurate{target_lang}。"
    user = (
        f"{translation_guide(target_lang)}\n\n"
        f"【Glossary (must be strictly followed)】\n{glossary_lines}\n\n"
    )
    if feedback:
        user += f"[Revision suggestions for this chapter (please modify accordingly)]\n{feedback}\n\n"
    user += (
        f"[Chapter to be translated: {chapter_name}】\n{chapter_text}\n\n"
        f"Please directly output the{target_lang}translation (Markdown) for this chapter, without additional explanation."
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    note = f"Translate {chapter_name}" + ("(Revised)" if feedback else "")
    return llm_chat(client, tracker, "Translation", messages, note=note)


def proofreading_agent(client, tracker, translations, glossary, target_lang="Chinese"):
    """
    Proofreading Agent: Receive all translations + glossary, perform consistency check
    (whether terminology is unified, whether there are contradictions, whether it is fluent), output a structured proofreading report (JSON).

    translations: {chapter_name: translation text}
    """
    glossary_lines = "\n".join(f'- {g["en"]} → {g["zh"]}' for g in glossary)
    joined = "\n\n".join(
        f"===== {name} =====\n{text}" for name, text in translations.items()
    )
    system = (
        f"You are a senior proofreader. Check the{target_lang}terminology consistency, cross-chapter consistency, and fluency of the translations."
        "Output only JSON."
    )
    user = (
        f"[Glossary]\n{glossary_lines}\n\n"
        f"[All Translations]\n{joined}\n\n"
        "Please output JSON:"
        '{"issues": [{"chapter": "chapter name", "type": "terminology inconsistency/contradiction/fluency", '
        '"detail": "issue description"}], "chapters_need_revision": ["chapter names needing revision"], '
        '"summary": "overall evaluation"}'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = llm_chat(
        client, tracker, "Proofreading", messages, json_mode=True, note="Consistency Proofreading"
    )
    return _loads_lenient(content)


def manager_decision(client, tracker, task, file_index, report):
    """
    A real LLM decision call by the Manager Agent.

    Key point: The Manager only sends a small context like "task + file index + proofreading report summary"
    to the model, to decide "which chapters need to be sent back to the Translation Agent for revision".
    It never puts the full translation into its own context — this is the approach to control Manager context bloat.
    """
    system = "You are the manager of the translation project, only making scheduling decisions, output JSON."
    user = (
        f"Task:{task}\n"
        f"File index (only store paths, not content):{json.dumps(file_index, ensure_ascii=False)}\n"
        f"Proofreading report summary:{json.dumps(report, ensure_ascii=False)}\n\n"
        "Based on the proofreading report, decide which chapters need revision. Output JSON:"
        '{"revise": ["chapter name", ...], "reason": "brief explanation"}'
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    content = llm_chat(
        client, tracker, "Manager", messages, json_mode=True, note="Scheduling Decision"
    )
    return _loads_lenient(content)


# ============================================================================
# Operation Mode 1: Orchestration Mode
# ============================================================================
def run_orchestration(chapters, out_dir, *, source_lang="English", target_lang="Chinese",
                      enable_glossary=True, enable_proofreading=True, trace=None):
    """
    chapters: ordered dictionary of {chapter_name: source text}
    out_dir: output directory (glossary, chapter translations, proofreading report all written here)

    Optional parameters:
      source_lang / target_lang: source language / target language (default English → Chinese, consistent with old behavior).
      enable_glossary: whether to enable Glossary Agent to extract glossary (if disabled, only editor-specified terms are kept).
      enable_proofreading: whether to enable Proofreading Agent + Manager revision loop.
      trace: optional callback trace(str), for printing real-time traces of the four-agent collaboration.

    Returns: metrics dictionary, including tracker, manager context peak, translation mapping, etc.
    """
    os.makedirs(out_dir, exist_ok=True)
    client = get_client()
    tracker = TokenTracker()
    emit = trace if callable(trace) else (lambda *a, **k: None)

    # ---- Manager's context: only stores these "lightweight" information, never contains full translations ----
    manager_context = {
        "task": f"Translate a{source_lang}technical booklet into fluent{target_lang}, ensuring terminology consistency throughout the book.",
        "guide": translation_guide(target_lang),
        "plan": list(ORCHESTRATION_PLAN),
        "call_log": [],       #  Agent invocation records (summary only, no content)
        "file_index": {},     #  File index: only store paths
        "progress": {},       #  Progress status
    }
    manager_peak = 0  #  Manager context (serialized state) token peak

    def snapshot_manager():
        nonlocal manager_peak
        size = count_tokens(json.dumps(manager_context, ensure_ascii=False))
        manager_peak = max(manager_peak, size)
        return size

    def log_call(agent, note, out_file, prompt_tokens, completion_tokens):
        #  Manager only records 'who did what, where the output is, how many tokens spent', not the content
        manager_context["call_log"].append(
            {
                "agent": agent,
                "note": note,
                "output": out_file,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        )
        snapshot_manager()

    snapshot_manager()
    emit("Manager: formulate plan and dispatch four specialized agents (each with independent context)")
    for step in manager_context["plan"]:
        emit(f"    Plan {step}")

    # ---- Step 1: Glossary Agent (independent context, read full book; release after output) ----
    book_text = "\n\n".join(f"# {n}\n{t}" for n, t in chapters.items())
    if enable_glossary:
        emit(f"Manager → Glossary Agent: read full book ({len(chapters)} chapters) extract shared glossary")
        glossary = glossary_agent(client, tracker, book_text, source_lang, target_lang)
    else:
        emit("Manager: skipped Glossary Agent (--no-glossary), only keep editorial-specified terms")
        glossary = []
    # Manager forcibly writes 'editorial-specified terms' into glossary (overwrite or add), as the unified contract for the whole book.
    for g in glossary:
        en = g["en"].strip().lower()
        if en in EDITORIAL_MANDATE:
            g["zh"] = EDITORIAL_MANDATE[en]
    present = {g["en"].strip().lower() for g in glossary}
    for en, zh in EDITORIAL_MANDATE.items():
        if en not in present:
            glossary.append({"en": en, "zh": zh, "pos": "Terms", "context": "Editorial-specified terms"})
    glossary_path = os.path.join(out_dir, "glossary.json")
    with open(glossary_path, "w", encoding="utf-8") as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
    # Manager only records paths in file index; glossary content stays in file system, not in Manager context
    manager_context["file_index"]["glossary"] = glossary_path
    # LLM usage is accounted only when Glossary Agent is actually invoked; no invocation when --no-glossary.
    g_prompt, g_completion = (
        (tracker.calls[-1]["prompt_tokens"], tracker.calls[-1]["completion_tokens"])
        if enable_glossary and tracker.calls else (0, 0)
    )
    log_call("Glossary", f"Extract {len(glossary)} terms", glossary_path,
             g_prompt, g_completion)
    if enable_glossary:
        emit(f"Glossary Agent ✓: determined {len(glossary)} terms → {os.path.basename(glossary_path)}"
             f" (Manager only records path, glossary content stays in file system)")
    else:
        emit(f"Manager: wrote {len(glossary)} editorial-specified terms → {os.path.basename(glossary_path)}")

    # ---- Step 2: Per-chapter Translation Agent (each chapter has an independent context instance) ----
    translations = {}
    for name, text in chapters.items():
        emit(f"Manager → Translation Agent: translate \"{name}\" (independent context, only sees this chapter + glossary)")
        zh = translation_agent(client, tracker, text, glossary, name,
                               source_lang=source_lang, target_lang=target_lang)
        # File name like chapter1_zh.md
        base = _slug(name)
        out_file = os.path.join(out_dir, f"{base}_zh.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(zh)
        translations[name] = zh
        manager_context["file_index"][name] = out_file
        manager_context["progress"][name] = "translated"
        last = tracker.calls[-1]
        log_call("Translation", f"Translate {name}", out_file,
                 last["prompt_tokens"], last["completion_tokens"])
        emit(f"Translation Agent ✓：{os.path.basename(out_file)}"
             f"(Context {last['prompt_tokens']} tok, translation written to disk, not returned to Manager)")

    # ---- Step 3: Proofreading Agent (reads all translations + glossary, independent context) ----
    if not enable_proofreading:
        emit("Manager: Skipped Proofreading Agent and revision loop (--no-proofreading)")
        report = {"issues": [], "chapters_need_revision": [],
                  "summary": "(Skipped proofreading)"}
        snapshot_manager()
        return {
            "mode": "orchestration",
            "tracker": tracker,
            "manager_context_peak": manager_peak,
            "manager_context_final": manager_context,
            "glossary": glossary,
            "translations": translations,
            "report": report,
            "out_dir": out_dir,
        }

    emit("Manager → Proofreading Agent: Read all translations + glossary for consistency/fluency review")
    report = proofreading_agent(client, tracker, translations, glossary, target_lang)
    report_path = os.path.join(out_dir, "proofreading_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    manager_context["file_index"]["report"] = report_path
    last = tracker.calls[-1]
    log_call("Proofreading", "Consistency Proofreading", report_path,
             last["prompt_tokens"], last["completion_tokens"])
    emit(f"Proofreading Agent ✓：{len(report.get('issues', []))} issues → "
         f"{os.path.basename(report_path)}")

    # ---- Step 4: Manager decision + at most one revision round ----
    # Manager only sends small context like "file index + report summary" to the model for decision
    report_summary = {
        "chapters_need_revision": report.get("chapters_need_revision", []),
        "issues": report.get("issues", [])[:5],
        "summary": report.get("summary", ""),
    }
    manager_context["progress"]["proofread"] = "done"
    snapshot_manager()

    emit("Manager: Read proofreading report summary (not the full text) → decide which sections need revision")
    decision = manager_decision(
        client, tracker, manager_context["task"],
        manager_context["file_index"], report_summary
    )
    revise = decision.get("revise", [])
    emit(f"Manager decision ✓: Sections needing revision {revise or 'None'}")

    for name in revise:
        if name not in chapters:
            continue
        # Find revision comments for that section
        fb = "; ".join(
            i.get("detail", "") for i in report.get("issues", [])
            if i.get("chapter") == name
        ) or "Please unify terminology according to the glossary and improve fluency."
        emit(f"Manager → Translation Agent: Revise \"{name}\" (with revision comments)")
        zh = translation_agent(client, tracker, chapters[name], glossary, name,
                               feedback=fb, source_lang=source_lang, target_lang=target_lang)
        base = _slug(name)
        out_file = os.path.join(out_dir, f"{base}_zh.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(zh)
        translations[name] = zh
        manager_context["progress"][name] = "revised"
        last = tracker.calls[-1]
        log_call("Translation", f"Revision {name}", out_file,
                 last["prompt_tokens"], last["completion_tokens"])

    snapshot_manager()
    emit(f"Manager: All done, output directory {out_dir}")

    return {
        "mode": "orchestration",
        "tracker": tracker,
        "manager_context_peak": manager_peak,
        "manager_context_final": manager_context,
        "glossary": glossary,
        "translations": translations,
        "report": report,
        "out_dir": out_dir,
    }


# ============================================================================
# Run mode 2: Single Agent mode (control group)
# ============================================================================
def run_single_agent(chapters, out_dir, *, source_lang="English", target_lang="Chinese"):
    """
    Naive baseline: one agent in a single growing conversation first skims the entire book,
    then translates chapter by chapter. No independent glossary tool to "pin down" terms, and context accumulates across chapters.

    This mode exposes two issues:
      - Context bloat: peak context of a single conversation = all content accumulated up to the last chapter;
      - Terminology drift: without a shared glossary constraint, the same term may be translated inconsistently across chapters.
    """
    os.makedirs(out_dir, exist_ok=True)
    client = get_client()
    tracker = TokenTracker()

    system = (
        f"You are a professional technical translator. I will give you a{source_lang}technical book chapter by chapter. Please translate each chapter into"
        f"fluent, accurate{target_lang}. Preserve Markdown structure; keep code in code blocks unchanged, do not translate."
    )
    # Single Agent's "main context": a continuously growing conversation
    messages = [{"role": "system", "content": system}]

    translations = {}
    for name, text in chapters.items():
        messages.append(
            {
                "role": "user",
                "content": f"Please translate the following chapter and output the Chinese translation directly: \n\n# {name}\n{text}",
            }
        )
        content = llm_chat(
            client, tracker, "SingleAgent", messages, note=f"Translate {name}"
        )
        # The translation remains in the conversation — this is the source of context bloat
        messages.append({"role": "assistant", "content": content})
        translations[name] = content
        base = _slug(name)
        out_file = os.path.join(out_dir, f"{base}_zh.md")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(content)

    return {
        "mode": "single_agent",
        "tracker": tracker,
        # Single Agent's "main context peak" = the largest prompt_tokens among all its calls
        "main_context_peak": tracker.by_agent()["SingleAgent"]["peak_context"],
        "translations": translations,
        "out_dir": out_dir,
    }
