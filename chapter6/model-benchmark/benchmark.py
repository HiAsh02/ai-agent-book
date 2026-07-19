"""
Multi-dimensional Model Performance Benchmark (Code for Experiments 6-8)

For multiple OpenAI-compatible LLM API providers, measure the following core metrics:
    - TTFT (Time To First Token)
    - End-to-end latency (from request to full response)
    - Throughput (tokens/s, based on generated output tokens; aggregate throughput / RPS under concurrency)
    - Standard deviation / p50 / p95 / p99 latency percentiles (high variance indicates unstable experience)
    - Availability / success rate (failures reduce availability but do not interrupt the entire table)

Two modes are supported:
    - Single-tier comparison: horizontal comparison table across multiple providers (default).
    - Concurrency scan (stress test): gradually increase concurrency for the same model, observing latency tail and aggregate throughput changes with concurrency.

Implementation highlights:
    - Use the streaming interface of the openai SDK (stream=True) to accurately measure TTFT.
    - Reuse the same OpenAI-compatible protocol via base_url, adapting to domestic APIs like Kimi / Doubao.
    - Single request failures are caught and recorded, without affecting other requests for the same (provider, model) or other providers — so a single run can measure the "availability" dimension.
"""

from __future__ import annotations

import os
import time
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Optional

from openai import OpenAI


# ---------------------------------------------------------------------------
# OpenRouter fallback: For "OpenAI native" entries (base_url empty), if the primary key is missing, route through OpenRouter.
# gpt-5.x direct connection to OpenAI requires organizational real-name authentication; as long as OPENROUTER_API_KEY exists, prefer OpenRouter.
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _to_openrouter_model(model: str) -> str:
    """Map model names to OpenRouter IDs: if contains '/' treat as native ID; gpt-* -> openai/*;
    claude-* -> anthropic/claude-opus-4.8; otherwise fallback to openai/gpt-5.6-luna."""
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------
@dataclass
class ProviderConfig:
    """Configuration for a single (provider, model) to test."""

    name: str                 # Display name, e.g., "OpenAI/gpt-5.6-luna"
    model: str                # Model name passed to the API
    api_key_env: str          # Environment variable name for reading the API key
    base_url: Optional[str] = None  # Leave empty for OpenAI official; fill in respective base_url for others

    def api_key(self) -> Optional[str]:
        return os.environ.get(self.api_key_env)

    def _openrouter_key(self) -> Optional[str]:
        return os.environ.get("OPENROUTER_API_KEY", "").strip() or None

    def resolve(self) -> tuple[Optional[str], Optional[str], str, bool]:
        """Resolve the actual (api_key, base_url, model, whether via OpenRouter).

        Only "OpenAI native" entries (base_url empty) participate in fallback; entries with a dedicated base_url
        (e.g., Kimi/Doubao) remain unchanged. Fallback rules:
          - gpt-5.x and has OPENROUTER_API_KEY -> prefer OpenRouter (direct connection requires real-name auth);
          - Otherwise, if primary key exists -> direct connection, model name unchanged;
          - Otherwise (OpenAI native + has OPENROUTER_API_KEY) -> route through OpenRouter, model name mapped.
        """
        primary = self.api_key()
        openai_native = self.base_url is None
        orkey = self._openrouter_key() if openai_native else None
        prefer_or = bool(orkey) and self.model.startswith("gpt-5")

        if not prefer_or and primary:
            return primary, self.base_url, self.model, False
        if orkey:
            return orkey, OPENROUTER_BASE_URL, _to_openrouter_model(self.model), True
        return primary, self.base_url, self.model, False

    def is_available(self) -> bool:
        """ Testable if primary key exists; OpenAI native entries can fallback to OpenRouter when primary key is missing."""
        if self.api_key():
            return True
        return self.base_url is None and self._openrouter_key() is not None


# By default, only run the three providers with valid keys.
# To extend, append ProviderConfig here (e.g., DeepSeek official vs SiliconFlow comparison).
DEFAULT_PROVIDERS: list[ProviderConfig] = [
    # OpenAI official (one key tests multiple models, observe differences across same vendor's tiers)
    # gpt-5.6-luna is the current cost-effective flagship; without OPENAI_API_KEY, automatically route through OpenRouter
    # (openai/gpt-5.6-luna); gpt-5.x will prefer OpenRouter as long as OPENROUTER_API_KEY exists.
    ProviderConfig(
        name="OpenAI/gpt-5.6-luna",
        model="gpt-5.6-luna",
        api_key_env="OPENAI_API_KEY",
    ),
    # Moonshot Kimi (OpenAI compatible)
    ProviderConfig(
        name="Moonshot/moonshot-v1-8k",
        model="moonshot-v1-8k",
        api_key_env="MOONSHOT_API_KEY",
        base_url="https://api.moonshot.cn/v1",
    ),
    # ByteDance Doubao / Volcano Engine (OpenAI compatible)
    ProviderConfig(
        name="Doubao/doubao-1.5-pro-32k",
        model="doubao-1-5-pro-32k-250115",
        api_key_env="ARK_API_KEY",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    ),
]


# ---------------------------------------------------------------------------
# Single Request Measurement
# ---------------------------------------------------------------------------
@dataclass
class RequestResult:
    """Measurement result of one streaming request."""

    ok: bool
    ttft: Optional[float] = None            # Time to first token (seconds)
    latency: Optional[float] = None         # End-to-end latency (seconds)
    completion_tokens: Optional[int] = None # Number of output tokens generated
    throughput: Optional[float] = None      # Output throughput (tokens/s)
    error: Optional[str] = None             # Failure reason (recorded when availability decreases)


def measure_once(
    client: OpenAI,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: float,
) -> RequestResult:
    """
    Initiate a streaming request and measure various metrics.

    Any exception is caught as a "failure" for availability statistics — never thrown upward,
    to avoid a single point of failure interrupting the entire table test.
    """
    start = time.perf_counter()
    first_token_at: Optional[float] = None
    completion_tokens = 0
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.0,
            stream=True,
            # Request usage statistics (some OpenAI-compatible services support; fallback to counting below if not supported)
            stream_options={"include_usage": True},
            timeout=timeout,
        )

        reported_tokens: Optional[int] = None
        for chunk in stream:
            # The arrival time of the first "content" chunk is TTFT
            if chunk.choices:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    if first_token_at is None:
                        first_token_at = time.perf_counter()
                    completion_tokens += 1  # Fallback counting: approximate token count via streaming chunks
            # If the service returns precise usage at the end, use it
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                reported_tokens = getattr(usage, "completion_tokens", None)

        end = time.perf_counter()

        if first_token_at is None:
            # Got a response but no content tokens, treat as failure
            return RequestResult(ok=False, error="empty response (no content token)")

        final_tokens = reported_tokens if reported_tokens else completion_tokens
        latency = end - start
        ttft = first_token_at - start
        # Throughput is calculated based on the "generation phase": output token count / (end-to-end - first token latency)
        gen_time = max(latency - ttft, 1e-6)
        throughput = final_tokens / gen_time if final_tokens else 0.0

        return RequestResult(
            ok=True,
            ttft=ttft,
            latency=latency,
            completion_tokens=final_tokens,
            throughput=throughput,
        )
    except Exception as exc:  # noqa: BLE001 —— Deliberate catch-all, any error counts as availability degradation
        return RequestResult(ok=False, error=f"{type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Aggregated results
# ---------------------------------------------------------------------------
@dataclass
class ProviderSummary:
    provider: str
    model: str
    total: int
    success: int
    results: list[RequestResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    concurrency: int = 1        # Concurrency used for this batch (used to annotate rows during concurrent scanning)
    wall_time: float = 0.0      # Wall-clock time for the entire batch (seconds), used to calculate aggregate throughput/RPS

    @property
    def availability(self) -> float:
        return self.success / self.total if self.total else 0.0

    @property
    def rps(self) -> Optional[float]:
        """ Throughput (requests/sec): number of successful requests / total wall-clock time of the batch. Higher concurrency generally increases throughput until hitting a ceiling."""
        if self.wall_time <= 0:
            return None
        return self.success / self.wall_time

    @property
    def agg_throughput(self) -> Optional[float]:
        """ Aggregate output throughput (tokens/s): total output tokens of all successful requests / total wall-clock time of the batch."""
        if self.wall_time <= 0:
            return None
        total_tokens = sum(
            r.completion_tokens for r in self.results
            if r.ok and r.completion_tokens
        )
        return total_tokens / self.wall_time if total_tokens else 0.0

    def _vals(self, attr: str) -> list[float]:
        return [getattr(r, attr) for r in self.results if r.ok and getattr(r, attr) is not None]

    @staticmethod
    def _pct(values: list[float], q: float) -> Optional[float]:
        """ Linear interpolation quantiles; falls back to min/max when sample size is too small."""
        if not values:
            return None
        s = sorted(values)
        if len(s) == 1:
            return s[0]
        pos = q * (len(s) - 1)
        lo = int(pos)
        hi = min(lo + 1, len(s) - 1)
        frac = pos - lo
        return s[lo] + (s[hi] - s[lo]) * frac

    def stat(self, attr: str, kind: str) -> Optional[float]:
        vals = self._vals(attr)
        if not vals:
            return None
        if kind == "mean":
            return statistics.mean(vals)
        if kind == "std":
            # Standard deviation: meaningless when sample size < 2, returns 0 instead of error
            return statistics.stdev(vals) if len(vals) >= 2 else 0.0
        if kind == "p50":
            return self._pct(vals, 0.50)
        if kind == "p95":
            return self._pct(vals, 0.95)
        if kind == "p99":
            return self._pct(vals, 0.99)
        raise ValueError(kind)


def benchmark_provider(
    cfg: ProviderConfig,
    prompt: str,
    num_requests: int,
    concurrency: int,
    max_tokens: int,
    timeout: float,
) -> ProviderSummary:
    """ Send num_requests requests (with concurrency) to a single provider."""
    # This is a latency benchmark: explicitly disable SDK auto-retry (max_retries=0), so that a timeout/hanging
    # request is truthfully recorded as a "failure" (counted as availability degradation), rather than being silently retried, which would inflate latency and
    # mask real failures. Each request still has a per-call timeout (see measure_once).
    # Add an additional client-level timeout as a safety net to prevent individual requests from hanging indefinitely and blocking the thread pool.
    # Parse the actually used credentials/endpoints/models (fall back to OpenRouter when OpenAI native entries lack a key).
    api_key, base_url, model, via_openrouter = cfg.resolve()
    if via_openrouter:
        print(f"    (Fallback to OpenRouter:{cfg.model} -> {model}）", flush=True)
    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=0,
    )
    results: list[RequestResult] = []

    batch_start = time.perf_counter()
    if concurrency <= 1:
        for _ in range(num_requests):
            results.append(measure_once(client, model, prompt, max_tokens, timeout))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [
                pool.submit(measure_once, client, model, prompt, max_tokens, timeout)
                for _ in range(num_requests)
            ]
            for fut in as_completed(futures):
                results.append(fut.result())
    wall_time = time.perf_counter() - batch_start

    success = sum(1 for r in results if r.ok)
    errors = [r.error for r in results if not r.ok and r.error]
    return ProviderSummary(
        provider=cfg.name,
        model=model,
        total=num_requests,
        success=success,
        results=results,
        errors=errors,
        concurrency=concurrency,
        wall_time=wall_time,
    )


def run_benchmark(
    providers: list[ProviderConfig],
    prompt: str,
    num_requests: int,
    concurrency: int,
    max_tokens: int,
    timeout: float,
) -> list[ProviderSummary]:
    """ Run benchmarks for each provider sequentially (providers are serial, concurrency is internal to a single provider)."""
    summaries: list[ProviderSummary] = []
    for cfg in providers:
        print(f"  → Testing {cfg.name} "
              f"(model={cfg.model}, N={num_requests}, concurrency={concurrency}) ...", flush=True)
        summary = benchmark_provider(
            cfg, prompt, num_requests, concurrency, max_tokens, timeout
        )
        print(f"    Done: success {summary.success}/{summary.total}", flush=True)
        summaries.append(summary)
    return summaries


def sweep_concurrency(
    cfg: ProviderConfig,
    prompt: str,
    num_requests: int,
    concurrency_levels: list[int],
    max_tokens: int,
    timeout: float,
) -> list[ProviderSummary]:
    """
    Stress test: gradually increase concurrency for the same (provider, model), return summary for each concurrency level.

    Corresponds to the book's "find the rate limit point by gradually increasing concurrency, record RPM/TPM limits"——
    As concurrency increases, single-request latency (p95) worsens, availability may drop due to rate limiting,
    while aggregate throughput (RPS / tokens·s⁻¹) first rises then plateaus (hitting the server-side limit).
    """
    summaries: list[ProviderSummary] = []
    for c in concurrency_levels:
        print(f"  → {cfg.name} @ concurrency={c} (N={num_requests}) ...", flush=True)
        summary = benchmark_provider(cfg, prompt, num_requests, c, max_tokens, timeout)
        print(f"    Done: success {summary.success}/{summary.total}, "
              f"Wall clock {summary.wall_time:.2f}s", flush=True)
        summaries.append(summary)
    return summaries


# ---------------------------------------------------------------------------
# Synthetic data: for offline demonstration of metric aggregation only, not a real benchmark
# ---------------------------------------------------------------------------
def synthetic_summary(
    provider: str,
    model: str,
    num_requests: int,
    concurrency: int,
    *,
    base_ttft: float = 0.30,
    base_gen_throughput: float = 90.0,
    fail_rate: float = 0.0,
    seed: int = 0,
) -> ProviderSummary:
    """
    Generate a batch of RequestResults that "look like real measurements" using pseudo-random numbers, used for:
      1) Verifying metric aggregation math (p50/p95/p99/std/availability) without API keys or network;
      2) Demonstrating the trend of worsening latency tail and possible availability drop as concurrency increases.

    ⚠️ All generated numbers are synthetic and do not represent the performance of any real model/provider.
    Higher concurrency increases TTFT and end-to-end latency using a simple queuing model, only to show the trend.
    """
    rng = random.Random(seed + concurrency * 1000)
    # Concurrency amplification factor: higher concurrency leads to longer queuing (simple linear + jitter model)
    contention = 1.0 + 0.12 * max(concurrency - 1, 0)

    results: list[RequestResult] = []
    total_tokens = 0
    sum_latency = 0.0
    for _ in range(num_requests):
        # Failure rate increases with concurrency (simulating rate limiting), capped at 60%
        eff_fail = min(fail_rate * contention, 0.60)
        if rng.random() < eff_fail:
            results.append(RequestResult(ok=False, error="synthetic: rate_limited (429)"))
            continue
        # TTFT: log-normal shape, right-skewed (long tail), multiplied by concurrency amplification
        ttft = base_ttft * contention * rng.lognormvariate(0.0, 0.35)
        gen_tp = max(base_gen_throughput * rng.uniform(0.75, 1.15), 1.0)
        tokens = rng.randint(28, 48)
        gen_time = tokens / gen_tp
        latency = ttft + gen_time
        total_tokens += tokens
        sum_latency += latency
        results.append(RequestResult(
            ok=True,
            ttft=ttft,
            latency=latency,
            completion_tokens=tokens,
            throughput=gen_tp,
        ))

    success = sum(1 for r in results if r.ok)
    # Synthetic wall clock: amortize the total latency of successful requests across concurrency to obtain a self-consistent batch duration
    wall_time = max(sum_latency / max(concurrency, 1), 1e-6)
    errors = [r.error for r in results if not r.ok and r.error]
    return ProviderSummary(
        provider=provider,
        model=model,
        total=num_requests,
        success=success,
        results=results,
        errors=errors,
        concurrency=concurrency,
        wall_time=wall_time,
    )
