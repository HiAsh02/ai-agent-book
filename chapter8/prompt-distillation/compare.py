"""
Prompt Distillation "Before vs After" quantitative comparison script.

This script addresses the core question of Experiments 7-8: after distilling a "long prompt + thinking teacher" into a "no prompt + direct answer student", how much is saved and how much quality is lost? It operates **without loading any LLM or connecting to the internet**, using real data to compute a before/after comparison table:

  1. Input cost (tokens): each teacher call requires the full language classification prompt (about a thousand tokens), while the student only needs the raw text to be classified. The token difference is the input cost saved per call.
  2. Task quality: directly reads evaluation_results.json produced by evaluate.py to obtain the student's agreement rate with teacher labels on the same inputs (i.e., distillation fidelity).
  3. Case-by-case examples: extracts several real samples and displays side-by-side: teacher tokens / student tokens / teacher label / student prediction / whether they match, making the before/after on multiple cases clear at a glance.

Design principle: all numbers come from real data and real tokenizers, no fabrication. Latency (sub-second response time) requires measurement on GPU; this script does not estimate it, only reporting offline-reproducible token cost and quality.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple


VALID_LABELS = ["ar", "de", "el", "en", "es", "fr", "hi", "ru", "tr", "ur", "vi", "zh", "ot"]


def load_prompt_template(source_file: str) -> str:
    """Extract the language classification prompt template used by teachers from create_data.py (avoid importing vllm)."""
    src = Path(source_file).read_text(encoding="utf-8")
    match = re.search(
        r'LANGUAGE_CLASSIFICATION_PROMPT\s*=\s*"""(.*?)"""',
        src,
        re.DOTALL,
    )
    if not match:
        raise ValueError(
            f"Cannot be found in {source_file}  found the LANGUAGE_CLASSIFICATION_PROMPT template, "
            f"Please specify the file containing this constant using --prompt_source."
        )
    return match.group(1)


def build_token_counter(tokenizer_name: Optional[str]) -> Tuple[Callable[[str], int], str]:
    """
    Construct a token counting function with priority fallback to ensure offline availability.

    Returns (counter, method_description):
      1) If --tokenizer is specified, use HuggingFace tokenizer for precise counting (on GPU machines, obtain the actual token count for Qwen).
      2) Otherwise, use tiktoken's o200k_base (GPT-4o/o1 tokenizer) for approximation, reproducible offline.
      3) Fall back to a rough heuristic of 'character count / 4', explicitly marked as an estimate.
    Each method is noted in the output, and approximate values are never presented as exact.
    """
    if tokenizer_name:
        try:
            from transformers import AutoTokenizer

            tok = AutoTokenizer.from_pretrained(tokenizer_name, trust_remote_code=True)
            return (lambda s: len(tok.encode(s))), f"HuggingFace tokenizer (exact): {tokenizer_name}"
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] Unable to load tokenizer {tokenizer_name}（{exc}), fallback to tiktoken.", file=sys.stderr)

    try:
        import tiktoken

        enc = tiktoken.get_encoding("o200k_base")
        return (lambda s: len(enc.encode(s))), "tiktoken o200k_base (approximate, reproducible offline)"
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] tiktoken is not available ({exc}), fallback to character heuristic.", file=sys.stderr)

    return (lambda s: max(1, len(s) // 4)), "Number of characters / 4 (rough estimate)"


def load_texts(test_file: str) -> List[str]:
    with open(test_file, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def load_teacher_labels(train_data_file: str) -> Dict[str, str]:
    """Read the mapping of text -> teacher labels from the distillation training data (teacher annotations)."""
    mapping: Dict[str, str] = {}
    if not Path(train_data_file).exists():
        return mapping
    with open(train_data_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            msgs = data.get("messages", [])
            if len(msgs) >= 2:
                mapping[msgs[0].get("content", "")] = msgs[1].get("content", "")
    return mapping


def load_eval_results(eval_file: str) -> Optional[Dict]:
    if not Path(eval_file).exists():
        return None
    with open(eval_file, "r", encoding="utf-8") as f:
        return json.load(f)


def truncate(text: str, width: int = 42) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= width else text[: width - 1] + "…"


def compare(
    prompt_template: str,
    texts: List[str],
    teacher_labels: Dict[str, str],
    eval_results: Optional[Dict],
    count_tokens: Callable[[str], int],
    token_method: str,
    num_examples: int,
) -> Dict:
    n = len(texts)

    # Fixed prompt overhead (template itself, excluding text to be classified)
    fixed_overhead = count_tokens(prompt_template.format(text=""))

    teacher_input_total = 0
    student_input_total = 0
    per_text_tokens: List[Tuple[int, int]] = []  # (teacher_tokens, student_tokens)
    for text in texts:
        teacher_prompt = prompt_template.format(text=text)
        t_tok = count_tokens(teacher_prompt)
        s_tok = count_tokens(text)
        teacher_input_total += t_tok
        student_input_total += s_tok
        per_text_tokens.append((t_tok, s_tok))

    teacher_avg = teacher_input_total / n
    student_avg = student_input_total / n
    reduction_pct = 100.0 * (1 - student_input_total / teacher_input_total)
    ratio = teacher_input_total / student_input_total if student_input_total else float("inf")

    #  Student predictions (aligned line by line with test_file)
    student_preds: Optional[List[Optional[str]]] = None
    accuracy = None
    correct = evaluated = None
    if eval_results:
        student_preds = eval_results.get("predictions")
        summary = eval_results.get("summary", {})
        accuracy = summary.get("accuracy")
        correct = summary.get("correct")
        evaluated = summary.get("evaluated")

    #  Case by case: prioritize covering different languages, and try to include consistent/inconsistent examples for each.
    examples: List[Dict] = []
    seen_labels = set()
    for idx, text in enumerate(texts):
        teacher_label = teacher_labels.get(text, "?")
        student_pred = (
            student_preds[idx] if student_preds and idx < len(student_preds) else None
        )
        key = teacher_label
        if key in seen_labels and len(examples) >= num_examples:
            continue
        if len(examples) >= num_examples:
            break
        if key in seen_labels:
            continue
        seen_labels.add(key)
        t_tok, s_tok = per_text_tokens[idx]
        examples.append(
            {
                "text": text,
                "teacher_tokens": t_tok,
                "student_tokens": s_tok,
                "teacher_label": teacher_label,
                "student_pred": student_pred,
                "match": (student_pred == teacher_label) if student_pred else None,
            }
        )

    return {
        "num_cases": n,
        "token_method": token_method,
        "fixed_prompt_overhead": fixed_overhead,
        "teacher_input_total": teacher_input_total,
        "teacher_input_avg": teacher_avg,
        "student_input_total": student_input_total,
        "student_input_avg": student_avg,
        "input_token_reduction_pct": reduction_pct,
        "teacher_student_ratio": ratio,
        "student_accuracy": accuracy,
        "student_correct": correct,
        "student_evaluated": evaluated,
        "examples": examples,
    }


def print_report(r: Dict) -> None:
    line = "=" * 78
    print("\n" + line)
    print("Prompt distillation: before vs after quantization comparison")
    print(line)
    print(f"Number of samples: {r['num_cases']}")
    print(f"Token counting method: {r['token_method']}")
    print(f"Fixed prompt overhead      : {r['fixed_prompt_overhead']} tokens (the template itself, which is repeatedly paid for each call)")

    print("\n" + "-" * 78)
    print("1. Input cost (input tokens per call)")
    print("-" * 78)
    print(f"{'dimension':<24}{'Teacher (long prompt + thinking)':>20}{'Student (no prompt)':>18}")
    print(f"{'Average input tokens per entry':<24}{r['teacher_input_avg']:>20.1f}{r['student_input_avg']:>18.1f}")
    print(f"{'Total input tokens':<24}{r['teacher_input_total']:>20,}{r['student_input_total']:>18,}")
    print(
        f"\n→ Input token reduction {r['input_token_reduction_pct']:.1f}%"
        f"(Teachers are students' {r['teacher_student_ratio']:.1f}  times)."
    )
    print("  On APIs billed by input token, this directly reduces cost proportionally; there are also unaccounted")
    print("  thinking (CoT) output tokens, so the actual gap is even larger. Latency needs to be measured on GPU, not estimated here.")

    print("\n" + "-" * 78)
    print("2. Task Quality (student's agreement rate with teacher on same inputs = distillation fidelity)")
    print("-" * 78)
    if r["student_accuracy"] is not None:
        print(
            f"Teacher (baseline): 100.00%    Student (after distillation): {r['student_accuracy'] * 100:.2f}%"
            f"  ({r['student_correct']}/{r['student_evaluated']})"
        )
        print(
            f"→ Student without prompts or thinking retains about {r['student_accuracy'] * 100:.1f}% of teacher's judgments,"
            f"quality loss about {(1 - r['student_accuracy']) * 100:.1f} percentage points."
        )
    else:
        print("evaluation_results.json not found (student not yet evaluated). Run evaluate.py first to generate,")
        print("then come back to this section. Missing this section does not affect the input cost comparison above.")

    print("\n" + "-" * 78)
    print(f"3. Case-by-case examples ({len(r['examples'])} examples)")
    print("-" * 78)
    print(f"{'Text to classify':<44}{'Teacher tok':>8}{'Student tok':>8}{'Teacher':>6}{'Student':>6}{'Agree':>6}")
    for ex in r["examples"]:
        if ex["match"] is None:
            mark = "—"
        else:
            mark = "✓" if ex["match"] else "✗"
        pred = ex["student_pred"] if ex["student_pred"] else "—"
        print(
            f"{truncate(ex['text']):<44}"
            f"{ex['teacher_tokens']:>8}{ex['student_tokens']:>8}"
            f"{ex['teacher_label']:>6}{pred:>6}{mark:>6}"
        )
    print(line + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Prompt Distillation \"Before vs After\" Quantitative Comparison: offline calculation of input cost, task quality, and case-by-case examples",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--test_file",
        type=str,
        default="./example-data/multilingual.txt",
        help="Text file to classify (one sentence per line), used as the input set for comparison",
    )
    parser.add_argument(
        "--train_data_file",
        type=str,
        default="./data/prompt_distillation_lang.jsonl",
        help="Distillation training data (teacher annotations), used to obtain teacher labels as quality baseline",
    )
    parser.add_argument(
        "--eval_results",
        type=str,
        default="./evaluation_results.json",
        help="Evaluation results produced by evaluate.py, used to read student agreement rate (optional)",
    )
    parser.add_argument(
        "--prompt_source",
        type=str,
        default="./create_data.py",
        help="Source file containing the teacher prompt template LANGUAGE_CLASSIFICATION_PROMPT",
    )
    parser.add_argument(
        "--tokenizer",
        type=str,
        default=None,
        help="Optional: HuggingFace tokenizer name/path (e.g., Qwen/Qwen3-30B-A3B-Instruct-2507)."
        "If specified, use it for exact counting; otherwise, approximate with tiktoken to ensure offline runnability",
    )
    parser.add_argument(
        "--num_examples",
        type=int,
        default=10,
        help="Number of case-by-case examples to display (try to cover different languages)",
    )
    parser.add_argument(
        "--output_file",
        type=str,
        default=None,
        help="Optional: path to save comparison results (including case-by-case examples) as JSON",
    )
    args = parser.parse_args()

    if not os.path.exists(args.test_file):
        raise FileNotFoundError(f"Text file to classify does not exist: {args.test_file}")
    if not os.path.exists(args.prompt_source):
        raise FileNotFoundError(f"Prompt template source file does not exist: {args.prompt_source}")

    prompt_template = load_prompt_template(args.prompt_source)
    texts = load_texts(args.test_file)
    teacher_labels = load_teacher_labels(args.train_data_file)
    eval_results = load_eval_results(args.eval_results)
    count_tokens, token_method = build_token_counter(args.tokenizer)

    if not teacher_labels:
        print(
            f"[warn] No teacher annotations read from {args.train_data_file}, teacher labels for individual cases will be displayed as '?'.",
            file=sys.stderr,
        )
    if eval_results is None:
        print(
            f"[warn] {args.eval_results} not found, only input cost comparison will be provided, skipping the quality column.",
            file=sys.stderr,
        )

    report = compare(
        prompt_template=prompt_template,
        texts=texts,
        teacher_labels=teacher_labels,
        eval_results=eval_results,
        count_tokens=count_tokens,
        token_method=token_method,
        num_examples=args.num_examples,
    )

    print_report(report)

    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📁 Comparison results saved to: {args.output_file}")


if __name__ == "__main__":
    main()
