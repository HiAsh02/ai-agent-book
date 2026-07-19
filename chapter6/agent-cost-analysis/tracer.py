"""
Self-built lightweight tracing / observability system.

The design follows the distributed tracing span tree model (see book 6.x "Agent Observability"):
    - One agent task = One Trace
    - Each LLM call / tool call = One Span
    - Span records: step, type, token usage (prompt/completion/cached), latency, cost

Usage:
    tracer = Tracer(client)
    resp = tracer.chat(step="turn-1", tool="query_order",
                       model=..., messages=..., temperature=0)
    tracer.print_breakdown()   # Print cost breakdown aggregated by step/tool

Offline replay (no model calls, only cost calculation):
    tracer = Tracer.from_records(records, pricing=..., name=...)
    # records contain canned token counts from previous real runs
"""

import time
from dataclasses import dataclass, asdict, field
from typing import List, Optional

from config import Pricing, default_pricing


def _percentile(values: List[float], q: float) -> float:
    """Nearest-rank percentile, avoiding numpy dependency. q ranges from 0 to 100."""
    if not values:
        return 0.0
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    rank = max(1, min(len(xs), int(round(q / 100.0 * len(xs) + 0.5))))
    return xs[rank - 1]


@dataclass
class Span:
    """A traced call (mainly LLM calls here)."""
    step: str                 # Logical step name, e.g., "turn-2"
    tool: str                 # Tool/action name associated with this step, used to attribute "which step is most expensive"
    kind: str = "llm"         # Span type: llm / tool
    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    # Cumulative tokens occupied by tool return results in this round's input (the same tool return is repeatedly billed in subsequent rounds).
    # Estimated by the upper layer using a tokenizer and filled in; read back from records during offline replay. -1 means unknown.
    tool_ctx_tokens: int = -1
    latency_s: float = 0.0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def uncached_prompt_tokens(self) -> int:
        return max(self.prompt_tokens - self.cached_tokens, 0)


class Tracer:
    """Wraps the OpenAI client, automatically recording usage/latency/cost for each LLM call."""

    def __init__(self, client=None, name: str = "trace",
                 pricing: Optional[Pricing] = None):
        self.client = client
        self.name = name
        self.pricing = pricing or default_pricing()
        self.spans: List[Span] = []

    # ---------- Collection ----------
    def chat(self, step: str, tool: str, tool_ctx_tokens: int = -1, **kwargs):
        """Make a traced chat.completions call.

        kwargs are passed through to the openai client (model / messages / temperature, etc.).
        tool_ctx_tokens: cumulative tokens occupied by tool return results in this round's input (optional, for cost attribution).
        Returns the raw OpenAI response object for the upper layer to extract content.
        """
        t0 = time.time()
        resp = self.client.chat.completions.create(**kwargs)
        latency = time.time() - t0

        usage = resp.usage
        # cached_tokens is hidden in prompt_tokens_details, use defensive reading
        cached = 0
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            cached = getattr(details, "cached_tokens", 0) or 0

        span = Span(
            step=step,
            tool=tool,
            kind="llm",
            prompt_tokens=usage.prompt_tokens,
            cached_tokens=cached,
            completion_tokens=usage.completion_tokens,
            tool_ctx_tokens=tool_ctx_tokens,
            latency_s=latency,
            cost_usd=self.pricing.cost_usd(
                usage.prompt_tokens, cached, usage.completion_tokens),
        )
        self.spans.append(span)
        return resp

    # ---------- Offline Replay (canned token counts → recalculate cost) ----------
    @classmethod
    def from_records(cls, records: List[dict], name: str = "trace",
                     pricing: Optional[Pricing] = None) -> "Tracer":
        """Rebuild a trace from previously recorded token usage and recalculate cost with given unit prices (no model calls)."""
        tr = cls(client=None, name=name, pricing=pricing)
        for r in records:
            span = Span(
                step=r.get("step", ""),
                tool=r.get("tool", ""),
                kind=r.get("kind", "llm"),
                prompt_tokens=int(r.get("prompt_tokens", 0)),
                cached_tokens=int(r.get("cached_tokens", 0)),
                completion_tokens=int(r.get("completion_tokens", 0)),
                tool_ctx_tokens=int(r.get("tool_ctx_tokens", -1)),
                latency_s=float(r.get("latency_s", 0.0)),
            )
            span.cost_usd = tr.pricing.cost_usd(
                span.prompt_tokens, span.cached_tokens, span.completion_tokens)
            tr.spans.append(span)
        return tr

    def to_records(self) -> List[dict]:
        """Export raw token usage for each step (for persisting as canned trace for offline replay)."""
        out = []
        for s in self.spans:
            d = asdict(s)
            d.pop("cost_usd", None)   # Cost is recalculated from unit prices, not persisted as fixed values
            out.append(d)
        return out

    # ---------- Aggregation ----------
    def total_cost(self) -> float:
        return sum(s.cost_usd for s in self.spans)

    def total_prompt_tokens(self) -> int:
        return sum(s.prompt_tokens for s in self.spans)

    def total_cached_tokens(self) -> int:
        return sum(s.cached_tokens for s in self.spans)

    def total_completion_tokens(self) -> int:
        return sum(s.completion_tokens for s in self.spans)

    def total_uncached_prompt_tokens(self) -> int:
        return sum(s.uncached_prompt_tokens for s in self.spans)

    def total_tool_ctx_tokens(self) -> int:
        return sum(s.tool_ctx_tokens for s in self.spans if s.tool_ctx_tokens >= 0)

    def total_latency(self) -> float:
        return sum(s.latency_s for s in self.spans)

    def cache_rate(self) -> float:
        pin = self.total_prompt_tokens()
        return self.total_cached_tokens() / pin if pin else 0.0

    def component_costs(self) -> dict:
        """Break down total cost into three cost components (corresponding to the book "Cost Components"):
            - Uncached input / Cached input / Output
        And the proportion of tool return injection tokens in the input side (if known)."""
        p = self.pricing
        uncached_in = self.total_uncached_prompt_tokens()
        cached_in = self.total_cached_tokens()
        out = self.total_completion_tokens()
        return {
            "uncached_input_cost": uncached_in / 1_000_000 * p.input_per_m,
            "cached_input_cost": cached_in / 1_000_000 * p.cached_per_m,
            "output_cost": out / 1_000_000 * p.output_per_m,
            "uncached_input_tokens": uncached_in,
            "cached_input_tokens": cached_in,
            "output_tokens": out,
            "tool_ctx_tokens": self.total_tool_ctx_tokens(),
        }

    def cost_distribution(self) -> dict:
        """Per-step cost distribution (p50/p95/p99). Corresponds to the book "Cost Distribution p50/p95/p99"."""
        costs = [s.cost_usd for s in self.spans]
        n = len(costs)
        return {
            "n": n,
            "mean": (sum(costs) / n) if n else 0.0,
            "p50": _percentile(costs, 50),
            "p95": _percentile(costs, 95),
            "p99": _percentile(costs, 99),
            "max": max(costs) if costs else 0.0,
        }

    # ---------- Print ----------
    def print_breakdown(self, title: Optional[str] = None):
        """Print a per-step cost breakdown table for an agent task, and indicate the most expensive step, cost composition, and distribution."""
        print()
        print(f"===== Cost Breakdown: {title or self.name} =====")
        header = (
            f"{'Step':<8} {'Tool/Action':<20} {'Input tok':>8} {'Cached tok':>8} "
            f"{'Tool tok':>8} {'Output tok':>8} {'Latency(s)':>8} {'Cost($)':>12}"
        )
        print(header)
        print("-" * len(header))
        for s in self.spans:
            tctx = s.tool_ctx_tokens if s.tool_ctx_tokens >= 0 else "-"
            print(
                f"{s.step:<8} {s.tool:<20} {s.prompt_tokens:>8} {s.cached_tokens:>8} "
                f"{str(tctx):>8} {s.completion_tokens:>8} {s.latency_s:>8.2f} "
                f"{s.cost_usd:>12.6f}"
            )
        print("-" * len(header))
        tctx_total = self.total_tool_ctx_tokens() if any(
            s.tool_ctx_tokens >= 0 for s in self.spans) else "-"
        print(
            f"{'Total':<8} {'':<20} {self.total_prompt_tokens():>8} "
            f"{self.total_cached_tokens():>8} {str(tctx_total):>8} "
            f"{self.total_completion_tokens():>8} "
            f"{self.total_latency():>8.2f} {self.total_cost():>12.6f}"
        )

        # Attribution: which step is the most expensive
        if self.spans:
            worst = max(self.spans, key=lambda s: s.cost_usd)
            total = self.total_cost()
            share = worst.cost_usd / total * 100 if total else 0
            print(
                f"\nMost expensive step → {worst.step} / {worst.tool}: "
                f"${worst.cost_usd:.6f} (of total cost {share:.1f}%）"
            )

        # Cost breakdown (uncached input / cached input / output)
        comp = self.component_costs()
        total = self.total_cost() or 1e-12
        print("Cost breakdown:")
        print(f"  Uncached input  {comp['uncached_input_tokens']:>8} tok  "
              f"${comp['uncached_input_cost']:.6f}  ({comp['uncached_input_cost']/total*100:.1f}%)")
        print(f"  Cached input    {comp['cached_input_tokens']:>8} tok  "
              f"${comp['cached_input_cost']:.6f}  ({comp['cached_input_cost']/total*100:.1f}%)")
        print(f"  Output        {comp['output_tokens']:>8} tok  "
              f"${comp['output_cost']:.6f}  ({comp['output_cost']/total*100:.1f}%)")
        if comp["tool_ctx_tokens"] > 0:
            print(f"  Of which cumulative input from 'tool return injection' {comp['tool_ctx_tokens']} tok "
                  f" (the same tool return is repeatedly billed in each subsequent round)")

        #  Per-step cost distribution
        dist = self.cost_distribution()
        print(f"Per-step cost distribution (n={dist['n']}): mean ${dist['mean']:.6f}  "
              f"p50 ${dist['p50']:.6f}  p95 ${dist['p95']:.6f}  p99 ${dist['p99']:.6f}")
