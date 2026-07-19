"""
Coding Agent: Read the system prompt file → Locate relevant rules → Generate precise search/replace edits → Actually rewrite the file.

It works the same way as real coding agents (e.g., Claude Code / Cursor):
Instead of having the model rewrite the entire file, the model produces a set of precise (old_str -> new_str) edits,
which are applied one by one via exact string replacement in the file; if an edit's old_str does not match,
the error is fed back to the model for retry. This makes modifications "code-level" and auditable (directly produces a diff).
"""

import difflib
from config import get_client, get_model, TEMPERATURE

#File editing tool exposed to the Coding Agent
EDIT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "apply_edits",
            "description": (
                "Apply a set of precise search/replace edits to the prompt file. Each edit provides an old_str"
                "(the unique original text fragment in the file) and a new_str (the replacement text)."
                "old_str must match the file content character by character exactly."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "edits": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "old_str": {"type": "string"},
                                "new_str": {"type": "string"},
                            },
                            "required": ["old_str", "new_str"],
                        },
                    },
                    "rationale": {
                        "type": "string",
                        "description": "Briefly describe how this change responds to human feedback.",
                    },
                },
                "required": ["edits"],
            },
        },
    }
]


def _apply_one(content: str, old_str: str, new_str: str) -> tuple[str, str | None]:
    """Attempt to apply one edit. On success return (new content, None), on failure return (original content, error message)."""
    count = content.count(old_str)
    if count == 0:
        return content, f"old_str not found in the file:{old_str[:60]!r}"
    if count > 1:
        return content, f"old_str appears {count} times (not unique):{old_str[:60]!r}"
    return content.replace(old_str, new_str, 1), None


def optimize_prompt(prompt_path: str, feedback: str, max_rounds: int = 3, verbose: bool = True) -> dict:
    """
    Have the Coding Agent rewrite the file pointed to by prompt_path (in-place overwrite) based on human feedback.

    Returns {"before": original text, "after": new text, "diff": unified diff text, "rationale": explanation}.
    """
    client = get_client()
    model = get_model()

    with open(prompt_path, "r", encoding="utf-8") as f:
        original = f.read()

    system = (
        "You are a senior prompt engineering Coding Agent. You will receive a system prompt file for an airline customer service agent,"
        "along with feedback from a human expert. Please locate the rules related to 'manual transfer',"
        "generate precise search/replace edits to improve them, then call the apply_edits tool to apply the modifications.\n"
        "Change objectives:\n"
        "1) Tighten the transfer boundary, clarifying only two cases: the passenger explicitly requests a human agent, and emergency safety situations;\n"
        "2) Delete or rewrite vague rules that induce 'excessive transfer' (e.g., 'transfer if uncertain or passenger is dissatisfied');\n"
        "3) Add a clear negative rule: never transfer due to policy disputes / passenger dissatisfaction; instead, first check policy,"
        "patiently explain, and provide compliant alternatives.\n"
        "Only modify parts related to transfer strategy; keep the rest as unchanged as possible."
    )

    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": (
                f"【Human Expert Feedback】\n{feedback}\n\n"
                f"【Current System Prompt File Content】\n---\n{original}\n---\n\n"
                "Please call apply_edits to submit your precise edits."
            ),
        },
    ]

    working = original
    rationale = ""

    for round_idx in range(max_rounds):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=EDIT_TOOLS,
            tool_choice={"type": "function", "function": {"name": "apply_edits"}},
            temperature=TEMPERATURE,
        )
        msg = resp.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            break

        # Process the (single) apply_edits call
        tc = msg.tool_calls[0]
        import json

        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        edits = args.get("edits", [])
        rationale = args.get("rationale", rationale)

        errors = []
        applied = 0
        for e in edits:
            working, err = _apply_one(working, e.get("old_str", ""), e.get("new_str", ""))
            if err:
                errors.append(err)
            else:
                applied += 1

        if verbose:
            print(f"  [round {round_idx + 1}] Submitted {len(edits)} edits, succeeded {applied}, failed {len(errors)}")

        if not errors:
            # All edits succeeded, writing to disk
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": "All edits have been successfully applied."}
            )
            break
        else:
            # Some failed: roll back to original text, feed errors back to model for retry (maintain atomicity of edits)
            working = original
            feedback_msg = (
                "The following edits could not be applied. Please correct and resubmit the complete edit list (note that old_str must match the file character by character):\n"
                + "\n".join(f"- {er}" for er in errors)
            )
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": feedback_msg})

    # Write to disk (overwrite prompt file in place)
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(working)

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            working.splitlines(keepends=True),
            fromfile="system_prompt.txt (before)",
            tofile="system_prompt.txt (after)",
        )
    )

    return {"before": original, "after": working, "diff": diff, "rationale": rationale}
