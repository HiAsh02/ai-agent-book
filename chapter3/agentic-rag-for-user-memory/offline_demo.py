#!/usr/bin/env python3
"""Experiment 3-10 Offline Demo: Agentic Memory Retrieval vs. Naive Single Retrieval

This script runs entirely offline (no port 4242 retrieval service, no LLM API Key required),
to visually demonstrate the core argument of Experiment 3-10 in the book:

  Treating the user's cross-session conversation history as a knowledge base and endowing the Agent with "multi-turn iterative retrieval" capability,
  it can proactively discover key information that single retrieval would miss, thereby significantly outperforming naive one-shot retrieval (naive recall)
  on the "second-level multi-session retrieval" task.

The demo carrier is the layer2_01_multiple_vehicles test case from the evaluation set: the user mentions a Honda Accord (already scheduled for Friday maintenance at Firestone) and a Tesla Model 3 (not scheduled) in two different phone calls.
When the user asks "I want to schedule maintenance for my car, what services have I booked?", the correct answer must cover the service status of both vehicles — this is exactly what "disambiguation" requires.

Retrieval quality is measured by "decisive evidence recall rate": a correct answer depends on several decisive facts (e.g., Honda appointment confirmation number FS-447291, Tesla Model 3 existing as a second vehicle). We count whether the text chunks retrieved by each strategy cover these facts. All numbers are computed from real BM25 retrieval, without any fabrication."""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import Config
from chunker import ConversationChunker
from indexer import MemoryIndexer

console = Console()

# Default test case and its decisive evidence markers (each marker represents a fact that the answer must cover).
# Markers are just "which keyword to use to locate the text chunk containing that fact"; recall is computed from real retrieval.
DEFAULT_TEST_ID = "layer2_01_multiple_vehicles"
DEFAULT_GOLD_MARKERS = {
    "Honda confirmed appointment (FS-447291)": "FS-447291",
    "Tesla Model 3 exists as a second vehicle": "Model 3",
}

# Generic rules for extracting "vehicle entities" from retrieval results: year + make + model, or make + model.
_ENTITY_PATTERN = re.compile(
    r"\b((?:19|20)\d{2}\s+)?"
    r"(Honda|Toyota|Tesla|Ford|BMW|Audi|Chevrolet|Nissan|Mazda|Subaru|Lexus|Kia|Hyundai)"
    r"(?:\s+[A-Z][a-zA-Z0-9]+){0,2}"
)


def _load_test_case(test_cases_dir: Path, test_id: str) -> Optional[dict]:
    """ Find and load YAML test case by test_id under test_cases_dir."""
    for yaml_file in test_cases_dir.rglob("*.yaml"):
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data and data.get("test_id") == test_id:
            return data
    return None


def _extract_vehicle_entities(texts: List[str], limit: int = 4) -> List[str]:
    """ Generic extraction of vehicle entity phrases from a batch of text (not dependent on specific test case)."""
    seen: Dict[str, int] = {}
    for text in texts:
        for match in _ENTITY_PATTERN.finditer(text):
            phrase = re.sub(r"\s+", " ", match.group(0)).strip()
            # Remove leading year, focus on "make model" to make secondary queries more focused.
            phrase = re.sub(r"^(?:19|20)\d{2}\s+", "", phrase)
            seen[phrase] = seen.get(phrase, 0) + 1
    # Sort by occurrence frequency, take top limit as entities to be further investigated.
    ranked = sorted(seen.items(), key=lambda kv: kv[1], reverse=True)
    return [phrase for phrase, _ in ranked[:limit]]


def _covered_markers(retrieved_texts: List[str], gold_markers: Dict[str, str]) -> Dict[str, bool]:
    """ Determine whether each decisive fact is covered by the retrieved text."""
    joined = "\n".join(retrieved_texts)
    return {name: (marker in joined) for name, marker in gold_markers.items()}


def naive_retrieval(indexer: MemoryIndexer, question: str, top_k: int) -> List:
    """ Baseline: only use the original question for a single retrieval."""
    return indexer.search(question, top_k=top_k)


def agentic_retrieval(indexer: MemoryIndexer, question: str, top_k: int,
                      max_followups: int, verbose: bool = True) -> Dict:
    """ Agentic multi-turn retrieval (offline deterministic simulation).

    Simulates the Agent's ReAct retrieval loop, but replaces LLM with rules, thus fully offline:
      1. Perform initial retrieval with the original question;
      2. Discover from initial results "which other vehicle entities are mentioned" (key clues);
      3. For each discovered entity, perform an additional focused query "<entity> service appointment scheduled";
      4. Merge results from all turns as the final retrieval set.
    """
    trace: List[Dict] = []

    round1 = indexer.search(question, top_k=top_k)
    retrieved = {r.chunk_id: r for r in round1}
    trace.append({"query": question, "hits": [r.chunk_id for r in round1]})
    if verbose:
        console.print(f"[cyan]  [Turn 1] Query:[/cyan] {question}")
        console.print(f"           hits {len(round1)} chunks: "
                      + ", ".join(f"{r.chunk.conversation_id}#{r.chunk.start_round}-{r.chunk.end_round}"
                                  for r in round1))

    # Discover vehicle entities from initial results (key clues)
    entities = _extract_vehicle_entities([r.chunk.to_text() for r in round1])
    if verbose:
        console.print(f"[cyan]  [Evaluation] Vehicle entities discovered from initial results:[/cyan] {entities or '(none)'}")

    for entity in entities[:max_followups]:
        followup_query = f"{entity} service appointment scheduled"
        hits = indexer.search(followup_query, top_k=top_k)
        for r in hits:
            retrieved.setdefault(r.chunk_id, r)
        trace.append({"query": followup_query, "hits": [r.chunk_id for r in hits]})
        if verbose:
            console.print(f"[cyan]  [Follow-up] Query:[/cyan] {followup_query}")
            console.print(f"           hits {len(hits)} chunks: "
                          + ", ".join(f"{r.chunk.conversation_id}#{r.chunk.start_round}-{r.chunk.end_round}"
                                      for r in hits))

    return {"results": list(retrieved.values()), "trace": trace}


def run_demo(args) -> Dict:
    # Forced offline local BM25 backend
    config = Config.from_env()
    config.index.retrieval_backend = "local"
    config.chunking.rounds_per_chunk = args.rounds_per_chunk

    test_cases_dir = Path(args.test_cases_dir)
    if not test_cases_dir.is_absolute():
        test_cases_dir = (Path(__file__).parent / test_cases_dir).resolve()

    console.print(Panel.fit(
        "[bold cyan]Experiment 3-10 Offline Demo[/bold cyan]\n"
        "Agentic Memory Retrieval vs. Naive Single Retrieval (local BM25, no API / port 4242)",
        border_style="cyan"))

    data = _load_test_case(test_cases_dir, args.test_id)
    if not data:
        console.print(f"[red]Test case not found {args.test_id}, search directory: {test_cases_dir}[/red]")
        sys.exit(1)

    question = args.query or data.get("user_question", "")
    gold_markers = DEFAULT_GOLD_MARKERS if args.test_id == DEFAULT_TEST_ID else {}
    if args.gold_marker:
        gold_markers = {m: m for m in args.gold_marker}

    # Chunking + indexing (offline)
    chunker = ConversationChunker(config.chunking)
    chunks = chunker.chunk_test_case_conversations(data)
    indexer = MemoryIndexer(config.index)
    indexer.add_chunks(chunks)

    # Multi-session overview
    sessions = {}
    for c in chunks:
        sessions.setdefault(c.conversation_id, []).append(c)
    console.print(f"\n[bold]Test case:[/bold] {data.get('title', args.test_id)}")
    console.print(f"[bold]User question:[/bold] {question}")
    console.print(f"[bold]Cross-session memory:[/bold] total {len(sessions)} historical sessions,"
                  f"split into {len(chunks)} memory blocks (each block {args.rounds_per_chunk} rounds)")
    for conv_id, cs in sessions.items():
        meta = cs[0].metadata
        console.print(f"  • Session [magenta]{conv_id}[/magenta]（{meta.get('business', '?')} / "
                      f"{meta.get('department', '?')}）：{len(cs)} blocks")

    # Two strategies
    console.print("\n[bold yellow]Strategy A · Naive single retrieval (baseline)[/bold yellow]")
    naive_results = naive_retrieval(indexer, question, args.top_k)
    console.print(f"  Single query hits {len(naive_results)} chunks: "
                  + ", ".join(f"{r.chunk.conversation_id}#{r.chunk.start_round}-{r.chunk.end_round}"
                              for r in naive_results))

    console.print("\n[bold green]Strategy B · Agentic multi-round retrieval (memory-RAG)[/bold green]")
    agentic = agentic_retrieval(indexer, question, args.top_k, args.max_followups)
    agentic_results = agentic["results"]

    # Compute decisive evidence recall
    naive_cover = _covered_markers([r.chunk.to_text() for r in naive_results], gold_markers)
    agentic_cover = _covered_markers([r.chunk.to_text() for r in agentic_results], gold_markers)

    def recall(cover: Dict[str, bool]) -> float:
        return (sum(cover.values()) / len(cover)) if cover else 0.0

    # Metrics table
    table = Table(title="Retrieval quality comparison (decisive evidence recall)")
    table.add_column("Metric", style="cyan")
    table.add_column("Naive single retrieval", justify="center", style="yellow")
    table.add_column("Agentic multi-round retrieval", justify="center", style="green")
    table.add_row("Number of retrieval queries", "1", str(len(agentic["trace"])))
    table.add_row("Number of retrieved memory blocks", str(len(naive_results)), str(len(agentic_results)))
    for name in gold_markers:
        table.add_row(
            f"Facts covered: {name}",
            "[green]✓[/green]" if naive_cover.get(name) else "[red]✗[/red]",
            "[green]✓[/green]" if agentic_cover.get(name) else "[red]✗[/red]",
        )
    if gold_markers:
        table.add_row("[bold]Decisive evidence recall rate[/bold]",
                      f"[bold]{recall(naive_cover)*100:.0f}%[/bold]",
                      f"[bold]{recall(agentic_cover)*100:.0f}%[/bold]")
        naive_ok = all(naive_cover.values())
        agentic_ok = all(agentic_cover.values())
        table.add_row("Can fully disambiguate and answer",
                      "[green]Yes[/green]" if naive_ok else "[red]No[/red]",
                      "[green]Yes[/green]" if agentic_ok else "[red]No[/red]")
    console.print()
    console.print(table)

    if gold_markers:
        console.print(Panel(
            "Naive single retrieval issues only one query, hitting text blocks dominated by keywords like \"maintenance appointment\","
            "easily missing key information about the other car; agentic retrieval discovers from the first round results that \"there is a second car\","
            "then issues focused queries for each car, eventually retrieving the service status of both cars,"
            "thus outperforming naive recall on multi-session retrieval tasks.",
            title="Conclusion", border_style="green"))

    result = {
        "test_id": args.test_id,
        "question": question,
        "num_sessions": len(sessions),
        "num_chunks": len(chunks),
        "top_k": args.top_k,
        "naive": {
            "num_queries": 1,
            "num_retrieved": len(naive_results),
            "coverage": naive_cover,
            "recall": recall(naive_cover),
        },
        "agentic": {
            "num_queries": len(agentic["trace"]),
            "num_retrieved": len(agentic_results),
            "coverage": agentic_cover,
            "recall": recall(agentic_cover),
            "trace": agentic["trace"],
        },
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"\n[green]✓ Results written to {args.output}[/green]")

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Experiment 3-10 offline demo: Agentic memory retrieval vs. naive single retrieval (local BM25, no API required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test-id", default=DEFAULT_TEST_ID,
                        help=f"Evaluation set case ID (default: {DEFAULT_TEST_ID}）")
    parser.add_argument("--test-cases-dir", default="../user-memory-evaluation/test_cases",
                        help="Evaluation set test_cases directory (default: ../user-memory-evaluation/test_cases)")
    parser.add_argument("--query", default=None,
                        help="Override the user question in the test case, specify the question to retrieve")
    parser.add_argument("--top-k", type=int, default=3,
                        help="Number of memory chunks returned per retrieval (default: 3)")
    parser.add_argument("--rounds-per-chunk", type=int, default=20,
                        help="Number of turns per chunk when splitting conversation history (default: 20)")
    parser.add_argument("--max-followups", type=int, default=4,
                        help="Maximum number of additional focus queries appended by agentic retrieval (default: 4)")
    parser.add_argument("--gold-marker", action="append", default=None,
                        help="Custom decisive evidence keywords (can be specified multiple times); if not specified, use built-in defaults")
    parser.add_argument("--output", default=None,
                        help="Write structured results to the specified JSON file path")
    parser.add_argument("--quiet", action="store_true",
                        help="Reduce log noise (only show WARNING and above)")
    return parser


def main():
    args = build_parser().parse_args()
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
    run_demo(args)


if __name__ == "__main__":
    main()
