"""
Agent loop with three tool discovery strategies (text/ReAct protocol).

Why use "text injection + text-parsed tool calls" instead of OpenAI native function calling?
—— This experiment aims to replicate exactly what the book describes: injecting 120+ tool schemas **all at once into the system prompt (tens of thousands of tokens)**,
   causing "instruction-following degradation" under extremely long contexts. The OpenAI native function-calling interface imposes strong
   constraints/optimizations on tool selection, so even with hundreds of tools, errors are rare, failing to demonstrate the degradation; whereas treating schemas as plain text stuffed into the prompt
   and letting the model output tool calls in JSON form is the true mechanism of the control group in the book, and only then can the degradation be observed.

Protocol: The model outputs exactly one JSON per step:
    {"thought": "...", "tool": "tool_name", "arguments": {...}}
When the task is complete, output:
    {"thought": "...", "tool": "finish", "arguments": {"answer": "..."}}

1) run_full_injection —— Control group (full injection)
   The system prompt lists all 126 tools as text. injected_tokens = token count of that tool list text.

2) run_retrieval_prefilter —— Second control group (retrieval pre-filtering)
   Perform a **one-shot** semantic retrieval based on the user's initial query, injecting only the top-n candidate tools into the system prompt.
   Tokens are significantly reduced, but one-shot matching cannot foresee cross-domain needs that emerge during execution (the limitation described in the book).

3) run_active_discovery —— Experimental group (active discovery)
   The system prompt lists only a few basic tools + the discover_tools meta-tool.
   When the model calls discover_tools(need), it returns 3-5 candidate tools via embedding similarity, appending their text list as a
   **user message** into the conversation (protecting the system prefix KV Cache), and updates the status bar with the available tool list.
   injected_tokens = token count of basic tools + discover_tools + the actually discovered and loaded tool list.
"""

import json
import re
from typing import Dict, List

import tiktoken

from discovery import ToolIndex  # noqa: F401  (type hint usage)
from tools_library import (ALL_TOOLS, BASE_TOOL_NAMES, TOOL_IMPLS,
                           TOOLS_BY_NAME)

try:
    _ENC = tiktoken.get_encoding("o200k_base")  # gpt-4o series encoding
except Exception:
    _ENC = tiktoken.get_encoding("cl100k_base")


# ---------------------------------------------------------------------------
# Tool list text rendering & token statistics
# ---------------------------------------------------------------------------

def render_tool(tool: Dict) -> str:
    """Render a single tool as a complete JSON schema text (consistent with the actual injection into the prompt)."""
    return json.dumps(tool["function"], ensure_ascii=False, indent=2)


def render_tools(tools: List[Dict]) -> str:
    return "\n".join(render_tool(t) for t in tools)


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text)) if text else 0


# discover_tools meta-tool (also presented to the model in text form)
DISCOVER_TOOL = {
    "type": "function",
    "function": {
        "name": "discover_tools",
        "description": ("Discover new tools: call this when no suitable specialized tool is available, describing the capability you need in one sentence of natural language"
                        "the system will use semantic retrieval to return the most matching specialized tools and their definitions, after which you can call them."),
        "parameters": {"type": "object",
                       "properties": {"need": {"type": "string"}}, "required": ["need"]},
    },
}

FINISH_TOOL_DESC = "- finish(answer: string): call after all subtasks are completed, providing the final answer."


_PROTOCOL = (
    "You must output exactly one JSON object per step, with no extra text, in the format:\n"
    '{"thought": "brief thought", "tool": "tool_name", "arguments": {key-value pairs}}\n'
    "The system will execute the tool and return the result to you, then you output the next step.\n"
    "If and only if all subtasks of the task have been completed using appropriate tools, output:"
    '{"thought": "...", "tool": "finish", "arguments": {"answer": "final answer"}}\n'
    "Note: Please choose the most matching 'specialized tool' for each subtask, rather than a generic search tool."
)


def _extract_json(text: str):
    """Extract the first JSON object from the model's reply."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    # Find the first { to the matching }
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _run_loop(client, model, system_prompt, task_prompt, available_names,
              on_discover=None, max_steps=10):
    """
    Text ReAct loop.
    available_names: set, the set of tool names currently allowed to be called (excluding discover_tools/finish).
      —— In active discovery mode, this grows dynamically with discover_tools.
    Returns (called_tools, trace, finished).
    """
    messages = [{"role": "system", "content": system_prompt},
                {"role": "user", "content": task_prompt}]
    called: List[str] = []
    trace: List[str] = []
    finished = False

    for _ in range(max_steps):
        try:
            resp = client.chat.completions.create(
                model=model, messages=messages, temperature=0)
        except Exception as e:
            # Some reasoning models (e.g., gpt-5.x) only support default temperature=1, in which case fall back to default and retry.
            if "temperature" in str(e):
                resp = client.chat.completions.create(
                    model=model, messages=messages)
            else:
                raise
        content = resp.choices[0].message.content or ""
        messages.append({"role": "assistant", "content": content})

        action = _extract_json(content)
        if action is None or "tool" not in action:
            trace.append(f"[Format error] Model did not output valid JSON: {content[:80]!r}")
            messages.append({"role": "user",
                             "content": "Your reply is not valid JSON. Please output only a JSON object in the specified format."})
            continue

        name = action.get("tool")
        args = action.get("arguments") or {}

        if name == "finish":
            trace.append(f"[finish] {str(args.get('answer',''))[:100]}")
            finished = True
            break

        if name == "discover_tools" and on_discover is not None:
            need = args.get("need", "")
            result_text, new_names = on_discover(need)
            called.append(name)
            trace.append(f"[discover_tools] need='{need}' -> {new_names}")
            available_names.update(new_names)
            messages.append({"role": "user", "content": result_text})
            continue

        # Normal tool call
        if name not in available_names:
            # This tool is currently unavailable (not yet discovered in active discovery / not selected in pre-filtering / or pure hallucination) —
            # not counted in called (not actually executed), so scoring can reflect the failure of this subtask.
            trace.append(f"[Unavailable] {name}")
            hint = ("This tool is currently unavailable."
                    + ("Please use discover_tools to discover the tool for the required capability." if on_discover else
                       "Please select an existing tool from the tool list."))
            messages.append({"role": "user", "content": hint})
            continue

        called.append(name)
        impl = TOOL_IMPLS.get(name)
        result = impl(args) if impl else json.dumps({"error": f"unknown tool {name}"})
        trace.append(f"[call] {name}({json.dumps(args, ensure_ascii=False)})")
        messages.append({"role": "user", "content": f"Tool {name} returns:{result}"})

    return called, trace, finished


# ---------------------------------------------------------------------------
#  Control group: full injection
# ---------------------------------------------------------------------------

def run_full_injection(client, model, task_prompt: str, tools: List[Dict] = None,
                       max_steps: int = 10) -> Dict:
    tools = tools if tools is not None else ALL_TOOLS
    tools_text = render_tools(tools) + "\n" + FINISH_TOOL_DESC
    injected = count_tokens(tools_text)
    system = (
        f"You are an intelligent assistant. Below is the full list of tools available to you (total {len(tools)} items)."
        "Please select the most appropriate tool based on the task. If the task contains multiple subtasks, ensure each subtask is handled.\n\n"
        "【Tool List】\n" + tools_text + "\n\n" + _PROTOCOL
    )
    available = {t["function"]["name"] for t in tools}
    called, trace, finished = _run_loop(client, model, system, task_prompt, available,
                                        max_steps=max_steps)
    return {"mode": "full_injection", "injected_tokens": injected,
            "num_tools_exposed": len(tools), "called": called,
            "trace": trace, "finished": finished}


# ---------------------------------------------------------------------------
#  Control group 2: retrieval pre-filtering ("retrieval-based pre-filtering" in the book)
#   — Perform a **one-time** semantic retrieval based on the user's initial query, injecting only the top-n candidate tools into the system prompt.
#      It sits between "full injection" and "active discovery": tokens are significantly reduced, but it only matches once, unable to foresee
#      cross-domain needs that emerge during task execution (the inherent limitation described in the book) — if the specialized tool required for the second subtask
#      is not selected by this retrieval, the model cannot invoke it, causing that subtask to fail.
# ---------------------------------------------------------------------------

def run_retrieval_prefilter(client, model, task_prompt: str, index, top_n: int = 10,
                            tools: List[Dict] = None, max_steps: int = 10) -> Dict:
    tools = tools if tools is not None else ALL_TOOLS
    tbn = {t["function"]["name"]: t for t in tools}
    hits = index.search(task_prompt, top_k=top_n)
    picked = [name for name, _ in hits if name in tbn]
    picked_tools = [tbn[n] for n in picked]
    tools_text = render_tools(picked_tools) + "\n" + FINISH_TOOL_DESC
    injected = count_tokens(tools_text)
    system = (
        f"You are an intelligent assistant. The system has pre-retrieved the following potentially relevant tools based on your task (total {len(picked_tools)} items)."
        "Please select appropriate tools from the list to complete the task. If a subtask cannot find a suitable tool in the list, please explain honestly.\n\n"
        "【Tool List】\n" + tools_text + "\n\n" + _PROTOCOL
    )
    available = set(picked)
    called, trace, finished = _run_loop(client, model, system, task_prompt, available,
                                        max_steps=max_steps)
    return {"mode": "retrieval_prefilter", "injected_tokens": injected,
            "num_tools_exposed": len(picked_tools), "prefiltered": picked,
            "called": called, "trace": trace, "finished": finished}


# ---------------------------------------------------------------------------
#  Experimental group: active discovery
# ---------------------------------------------------------------------------

def run_active_discovery(client, model, task_prompt: str, index, top_k=4,
                         tools: List[Dict] = None, max_steps: int = 10) -> Dict:
    tools = tools if tools is not None else ALL_TOOLS
    tbn = {t["function"]["name"]: t for t in tools}
    base_tools = [tbn[n] for n in BASE_TOOL_NAMES]
    base_text = (render_tools(base_tools) + "\n"
                 + render_tool(DISCOVER_TOOL) + "\n" + FINISH_TOOL_DESC)

    discovered_names = set()          #  Specialized tools actually discovered and loaded in this round
    discovered_texts: List[str] = []  #  Corresponding text list (for counting on-demand injected tokens)
    available = set(BASE_TOOL_NAMES)

    def on_discover(need: str):
        hits = index.search(need, top_k=top_k)
        names, lines = [], []
        for name, score in hits:
            if name in BASE_TOOL_NAMES:
                continue
            names.append(name)
            lines.append(render_tool(tbn[name]) + f"   (similarity {score:.3f})")
            if name not in discovered_names:
                discovered_names.add(name)
                discovered_texts.append(render_tool(tbn[name]))
        status = f"\n\n【Status Bar｜Currently Available Tools】{sorted(available | set(names))}"
        body = ("discover_tools matched the following specialized tools, which have been loaded and can be called directly:\n"
                + "\n".join(lines) + status)
        return body, names

    system = (
        "You are an intelligent assistant. You currently only have a small set of basic tools (see below)."
        "When a task requires capabilities you do not have, first call discover_tools, describe the capability you need in natural language,"
        "the system will return and load the matching specialized tools, then you can call them."
        "If the task contains multiple subtasks (e.g., both query and download), call discover_tools for each capability separately,"
        "and before finishing, ensure each subtask has been completed with appropriate tools.\n\n"
        "【Basic Tools】\n" + base_text + "\n\n" + _PROTOCOL
    )
    called, trace, finished = _run_loop(client, model, system, task_prompt,
                                        available, on_discover=on_discover,
                                        max_steps=max_steps)

    injected = count_tokens(base_text) + count_tokens("\n".join(discovered_texts))
    return {"mode": "active_discovery", "injected_tokens": injected,
            "num_tools_exposed": len(BASE_TOOL_NAMES) + 1 + len(discovered_names),
            "discovered": sorted(discovered_names),
            "called": called, "trace": trace, "finished": finished}
