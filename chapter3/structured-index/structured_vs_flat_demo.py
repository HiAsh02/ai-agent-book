"""
Structured Index vs Flat Retrieval: An Offline Comparative Demo.

This module does not depend on OpenAI / vector models / network, and can run with pure Python + networkx.
It uses a manually curated small knowledge base of the "Intel x86 SIMD Instruction Set" to intuitively compare two retrieval approaches:

  * Flat Retrieval: Treat each knowledge point as an independent text chunk, and recall by word-level similarity scoring.
    This is an abstraction of traditional RAG "document chunking + vector retrieval" — it can only return scattered fragments.
  * Structured Retrieval:
      - GraphRAG-style entity-relation graph: performs multi-hop traversal along relation edges, capable of answering relational questions like "What connects A and B?" that flat retrieval cannot handle (corresponding to "multi-hop relational reasoning" in the book).
      - RAPTOR-style hierarchical tree: aggregates details into higher-level summaries, capable of answering macro questions like "Overview of a topic" that require cross-fragment synthesis (corresponding to "multi-level navigation" in the book).

This demo corresponds to the "Comparative Study of Knowledge Representation Philosophy" in Experiment 3-8 (structured-index).
Building a real index requires calling an LLM (see main.py build), but this demo pre-writes the index results manually so that readers can see "what problems structured indexing solves for flat retrieval" without needing an API Key.
"""

import json
import re
from collections import deque
from typing import Dict, List, Optional, Tuple

import networkx as nx


# ---------------------------------------------------------------------------
# Manually curated small knowledge base (corresponding to the Intel x86 example document in test_indexing.py)
# Each entity's description also serves as "a text chunk for flat retrieval".
# ---------------------------------------------------------------------------

ENTITIES: Dict[str, Dict[str, str]] = {
    "ADDPS": {"type": "instruction",
              "desc": "ADDPS: Performs parallel addition on packed single-precision floating-point numbers, processing four lanes of single-precision floating-point operations at once."},
    "MOVAPS": {"type": "instruction",
               "desc": "MOVAPS: Moves 128-bit packed single-precision floating-point data between vector registers and aligned memory."},
    "VADDPS": {"type": "instruction",
               "desc": "VADDPS: AVX version of packed single-precision floating-point addition, processing eight lanes of single-precision floating-point operations at once."},
    "CPUID": {"type": "instruction",
              "desc": "CPUID: Returns processor identification and feature information, used to detect whether the processor supports SSE, AVX, and other extensions."},
    "SSE": {"type": "extension",
            "desc": "SSE (Streaming SIMD Extensions): Introduces 128-bit vector registers, supporting packed single-precision floating-point parallel operations."},
    "AVX": {"type": "extension",
            "desc": "AVX (Advanced Vector Extensions): Extends vector registers to 256 bits, further enhancing SIMD capabilities."},
    "XMM": {"type": "register",
            "desc": "XMM0-XMM15: 128-bit vector registers used by SSE instructions to hold packed data."},
    "YMM": {"type": "register",
            "desc": "YMM0-YMM15: 256-bit vector registers used by AVX instructions, with the lower 128 bits shared with XMM registers."},
    "CR4.OSFXSR": {"type": "control-bit",
                   "desc": "CR4.OSFXSR: Control bit for operating system support of FXSAVE/FXRSTOR; must be set to 1 to allow SSE instructions."},
    "CR0.EM": {"type": "control-bit",
               "desc": "CR0.EM: Emulation flag; when set to 1, SIMD is disabled; must be cleared to execute SSE/AVX instructions."},
}

# Entity-relation triples (subject, relation, object) forming the knowledge graph of GraphRAG.
TRIPLES: List[Tuple[str, str, str]] = [
    ("ADDPS", "belongs to", "SSE"),
    ("MOVAPS", "belongs to", "SSE"),
    ("VADDPS", "belongs to", "AVX"),
    ("ADDPS", "operates", "XMM"),
    ("VADDPS", "operates", "YMM"),
    ("SSE", "uses register", "XMM"),
    ("AVX", "uses register", "YMM"),
    ("AVX", "extends from", "SSE"),
    ("SSE", "requires enabling", "CR4.OSFXSR"),
    ("AVX", "requires enabling", "CR4.OSFXSR"),
    ("SSE", "requires clearing", "CR0.EM"),
    ("CPUID", "detects", "SSE"),
    ("CPUID", "detects", "AVX"),
]

# RAPTOR-style hierarchical tree: aggregates fine-grained leaves into higher-level summaries (parent nodes).
TREE_SUMMARY = {
    "id": "SIMD Instruction Set Overview",
    "summary": ("x86 SIMD instruction sets started with MMX; SSE introduced 128-bit XMM vector registers and supported packed"
                "single-precision floating-point operations; AVX further extended registers to 256-bit YMM, increasing the parallel width of single-instruction multiple-data"
                "generation by generation; before use, enable via CR0/CR4 control bits and detect support with CPUID."),
    "children": ["ADDPS", "MOVAPS", "VADDPS", "SSE", "AVX", "XMM", "YMM"],
}


# ---------------------------------------------------------------------------
# Flat retrieval: treats each entity description as an independent text chunk, recalled by word-level similarity (cosine of word frequencies).
# This is a deterministic proxy for "vector retrieval" in offline scenarios: no internal structure, only the fragment itself.
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    """Coarse-grained tokenization: ASCII words (e.g., ADDPS, CR4, XMM) are kept intact; Chinese characters are split by individual characters."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    tokens += re.findall(r"[一-鿿]", text)
    return tokens


def _cosine(a: Dict[str, int], b: Dict[str, int]) -> float:
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = sum(v * v for v in a.values()) ** 0.5
    nb = sum(v * v for v in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


class FlatRetriever:
    """Recall independent text chunks by word surface similarity (simulating flat vector retrieval)."""

    def __init__(self, entities: Dict[str, Dict[str, str]]):
        self.docs = {name: e["desc"] for name, e in entities.items()}
        self.types = {name: e["type"] for name, e in entities.items()}
        self._vecs = {name: self._tf(text) for name, text in self.docs.items()}

    @staticmethod
    def _tf(text: str) -> Dict[str, int]:
        vec: Dict[str, int] = {}
        for tok in _tokenize(text):
            vec[tok] = vec.get(tok, 0) + 1
        return vec

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        qvec = self._tf(query)
        scored = [
            {"name": name, "type": self.types[name],
             "desc": self.docs[name], "score": _cosine(qvec, self._vecs[name])}
            for name in self.docs
        ]
        scored.sort(key=lambda r: r["score"], reverse=True)
        return scored[:top_k]


# ---------------------------------------------------------------------------
# Structured retrieval: multi-hop traversal over entity-relation graphs (core capability of GraphRAG).
# ---------------------------------------------------------------------------

def build_graph(triples: List[Tuple[str, str, str]]) -> nx.DiGraph:
    g = nx.DiGraph()
    for name, meta in ENTITIES.items():
        g.add_node(name, **meta)
    for src, rel, dst in triples:
        g.add_edge(src, dst, rel=rel)
    return g


def multi_hop_paths(graph: nx.DiGraph, start: str, max_hops: int = 3) -> List[List[Tuple[str, str, str]]]:
    """Starting from start, perform BFS along relation edges, returning all relation paths with <= max_hops hops.

    Each path is a list of (source entity, relation, target entity) steps. This is exactly what flat retrieval cannot express:
    'traversal along relation edges' — corresponding to the book's statement that 'knowledge graphs naturally support traversal along relation edges, making multi-hop queries efficient and reliable'.
    """
    if start not in graph:
        return []
    paths: List[List[Tuple[str, str, str]]] = []
    # Queue element: (current node, path to reach this node)
    queue: deque = deque([(start, [])])
    while queue:
        node, path = queue.popleft()
        if len(path) >= max_hops:
            continue
        for nbr in graph.successors(node):
            step = (node, graph[node][nbr]["rel"], nbr)
            new_path = path + [step]
            paths.append(new_path)
            queue.append((nbr, new_path))
    return paths


def match_entity(graph: nx.DiGraph, query: str) -> Optional[str]:
    """Find the starting entities appearing in the query (by longest name match, deterministic)."""
    q = query.lower()
    hits = [name for name in graph.nodes if name.lower() in q]
    return max(hits, key=len) if hits else None


def format_path(path: List[Tuple[str, str, str]]) -> str:
    if not path:
        return ""
    parts = [path[0][0]]
    for src, rel, dst in path:
        parts.append(f" --{rel}--> {dst}")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Three demo queries: highlighting three shortcomings of flat retrieval.
# ---------------------------------------------------------------------------

def demo_multi_hop(flat: FlatRetriever, graph: nx.DiGraph, query: str, top_k: int) -> None:
    print(f"\n【Query 1｜Multi-hop Relation Reasoning】{query}")
    print("-- Flat retrieval (returns independent fragments by word surface similarity) --")
    for i, r in enumerate(flat.search(query, top_k), 1):
        print(f"  {i}. [{r['type']}] {r['name']}  (score={r['score']:.3f})")
    print("  ✗ Can only recall isolated fragments with similar wording, unable to 'connect' ADDPS to a specific control bit —"
          "without relations, it cannot determine which control bit is the answer for ADDPS.")

    print("-- Structured graph retrieval (multi-hop traversal along relation edges) --")
    start = match_entity(graph, query)
    paths = multi_hop_paths(graph, start, max_hops=3)
    #  Only show paths ending at control bits (the question asks about 'control register bits')
    answers = [p for p in paths if graph.nodes[p[-1][2]]["type"] == "control-bit"]
    for p in answers:
        print(f"  {format_path(p)}")
    enable = [p for p in answers if p[-1][1] == "requires enabling"]
    if enable:
        target = enable[0][-1][2]
        print(f"  ✓ Answer:{target}(Reachable from {start} via {len(enable[0])} hops)")
        print(f"    {graph.nodes[target]['desc']}")


def demo_compare(flat: FlatRetriever, graph: nx.DiGraph, query: str, top_k: int) -> None:
    print(f"\n【Query 2｜Cross-Node Comprehensive Comparison】{query}")
    print("-- Flat retrieval --")
    for i, r in enumerate(flat.search(query, top_k), 1):
        print(f"  {i}. [{r['type']}] {r['name']}  (score={r['score']:.3f})")
    print("  ✗ Facts about SSE and AVX registers are scattered across different fragments; flat retrieval recalls them separately,"
          "but does not actively align 'who uses which register' into a comparison table.")

    print("-- Structured graph retrieval (traverse along 'uses register' edge to retrieve facts on both sides) --")
    for ext in ("SSE", "AVX"):
        regs = [dst for _, dst, d in graph.out_edges(ext, data=True) if d["rel"] == "uses register"]
        for reg in regs:
            print(f"  {ext} --uses register--> {reg}：{graph.nodes[reg]['desc']}")
    print("  ✓ By traversing two entities along the same relation edge, we can directly synthesize the comparison: 'SSE=128-bit XMM, AVX=256-bit YMM'.")


def demo_hierarchical(flat: FlatRetriever, query: str, top_k: int) -> None:
    print(f"\n【Query 3｜Multi-Level Navigation (RAPTOR Hierarchy Tree)】{query}")
    print("-- Flat retrieval --")
    for i, r in enumerate(flat.search(query, top_k), 1):
        print(f"  {i}. [{r['type']}] {r['name']}  (score={r['score']:.3f})")
    print("  ✗ Recalls scattered detail fragments, too granular to answer macro-level questions like 'overview' that require cross-fragment synthesis.")

    print("-- Structured tree retrieval (return upper-level summary nodes) --")
    print(f"  [Parent node summary] {TREE_SUMMARY['id']}")
    print(f"  {TREE_SUMMARY['summary']}")
    print(f"  ✓ Start from a macro summary, then drill down to {', '.join(TREE_SUMMARY['children'][:4])} and other leaf nodes when details are needed.")


def run_demo(top_k: int = 3, custom_query: Optional[str] = None,
             output: Optional[str] = None) -> Dict:
    """Run offline comparison demo; return structured results (for --output persistence)."""
    flat = FlatRetriever(ENTITIES)
    graph = build_graph(TRIPLES)

    print("=" * 68)
    print("Structured Index vs Flat Retrieval · Offline Comparison Demo (No API Key Required)")
    print(f"Knowledge Base: Intel x86 SIMD Instruction Set  |  Entity {graph.number_of_nodes()} entities, "
          f"relations {graph.number_of_edges()} , 1 hierarchy tree")
    print("=" * 68)

    if custom_query:
        # Custom Query: Provides both flat and graph retrieval perspectives
        print(f"\n【Custom Query】{custom_query}")
        print("-- Flat retrieval --")
        flat_hits = flat.search(custom_query, top_k)
        for i, r in enumerate(flat_hits, 1):
            print(f"  {i}. [{r['type']}] {r['name']}  (score={r['score']:.3f})")
        print("-- Structured Graph Retrieval (Multi-hop traversal of entities identified from the query) --")
        start = match_entity(graph, custom_query)
        if start is None:
            print("  (No known entities identified in the query, unable to perform graph traversal)")
            paths = []
        else:
            paths = multi_hop_paths(graph, start, max_hops=3)
            for p in paths:
                print(f"  {format_path(p)}")
        result = {"query": custom_query,
                  "flat": [{"name": r["name"], "score": r["score"]} for r in flat_hits],
                  "graph_start": start,
                  "graph_paths": [format_path(p) for p in paths]}
    else:
        q1 = "Before executing the ADDPS instruction, which control register bit must the operating system set to 1?"
        q2 = "What is the difference between the vector registers used by SSE and AVX?"
        q3 = "Overview of the x86 SIMD instruction set"
        demo_multi_hop(flat, graph, q1, top_k)
        demo_compare(flat, graph, q2, top_k)
        demo_hierarchical(flat, q3, top_k)
        start1 = match_entity(graph, q1)
        result = {
            "queries": [q1, q2, q3],
            "multi_hop": {
                "query": q1,
                "start": start1,
                "paths": [format_path(p) for p in multi_hop_paths(graph, start1, 3)
                          if graph.nodes[p[-1][2]]["type"] == "control-bit"],
            },
        }

    print("\n" + "=" * 68)
    print("Conclusion: Flat retrieval excels at 'finding fragments containing certain information', but once a query requires cross-fragment relational reasoning or"
          "multi-level synthesis, it must rely on structured indexing (graph/hierarchy tree). — Corresponds to the core point of Experiment 3-8 in the book.")
    print("=" * 68)

    if output:
        with open(output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nResults written to:{output}")
    return result


if __name__ == "__main__":
    run_demo()
