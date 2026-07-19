"""
Simulated "Multiple Websites/Information Sources"
=======================

Experiment 10-6 emphasizes "parallel search by multiple homogeneous agents + central coordination"; the browser itself is not the focus.
Therefore, a set of **controllable simulated data sources** is used instead of real browsers:

- Each Source corresponds to a "website", with a name, content, and a controllable access delay;
- ``fetch()`` simulates "opening a website and scraping", using ``asyncio.sleep`` to create varying time costs,
  making "who hits first" reproducible (and also making cascading termination/race conditions appear stably);
- Whether the target answer is included is determined by ``holds_answer``.

The delays are deliberately designed: two sources hit almost simultaneously, stably triggering a "race" demonstration.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Source:
    name: str            # "Website" name
    latency: float       # Single-step fetch delay (seconds), simulating network/rendering time
    content: str         # Searchable text of the website
    holds_answer: bool   # Whether the website actually contains the target answer

    async def fetch(self) -> str:
        """Simulate a fetch: wait for latency then return content."""
        await asyncio.sleep(self.latency)
        return self.content


# —— Demo task: parallel search for "Which is the highest mountain in the world and what is its altitude?" ——
# Only some sources contain the exact answer; the delays of the two correct sources are designed to be very close, creating a race condition.
QUESTION = "What is the highest mountain in the world and what is its approximate altitude?"
ANSWER_KEYWORDS = ["Mount Everest", "Everest", "Everest", "8848"]

DEMO_SOURCES: List[Source] = [
    Source("baike-wiki", 0.9, "Encyclopedia entry: The Himalayas stretch across the southern edge of the Qinghai-Tibet Plateau.", False),
    Source("news-portal", 1.1, "News portal: Multiple mountaineering teams plan to climb high-altitude peaks recently.", False),
    Source("geo-journal", 0.6, "Geography journal: The world's highest peak is Mount Everest, with an altitude of about 8848 meters, located on the China-Nepal border.", True),
    Source("travel-blog", 1.4, "Travel blog: The author shares experiences of trekking to the base camp in Nepal.", False),
    # Same delay as geo-journal: the two correct sources will hit almost simultaneously, stably triggering a race condition.
    Source("forum-qa", 0.6, "Q&A community: Netizens discuss that the highest peak is actually Mount Everest, with an official altitude of 8848.86 meters.", True),
    Source("edu-site", 1.2, "Educational website: Introduces how plate movements uplifted tall mountain ranges.", False),
    Source("gov-data", 1.6, "Government data: Published survey parameters and coordinate information for several peaks.", False),
    Source("random-blog", 0.8, "Personal blog: Random notes about a snow mountain photography trip.", False),
    Source("science-mag", 1.3, "Science magazine: Explains the effects of high-altitude hypoxia on the human body.", False),
    Source("map-service", 1.0, "Map service: Can query contour lines and terrain profiles of various peaks.", False),
]


def keyword_judge(text: str) -> Optional[str]:
    """
    Controllable "judge whether answer is hit" logic (does not rely on LLM):
    If any keyword is hit, the answer is considered found, and the extracted answer sentence is returned; otherwise, None is returned.
    """
    for kw in ANSWER_KEYWORDS:
        if kw in text:
            # Simply return the sentence containing the keyword as the answer
            for sentence in text.replace("。", "。\n").splitlines():
                if kw in sentence:
                    return sentence.strip("：: ")
            return text
    return None


def build_sources(n: int) -> List[Source]:
    """
    Construct n parallel sources, allowing command-line ``--agents N`` to dynamically adjust the number of parallel agents.

    Design constraints (to ensure the demo is always reproducible):
    - When n == 10, **return** ``DEMO_SOURCES`` as-is, default behavior exactly as before;
    - When n >= 2, always include two sources that "contain the answer and have the same delay" (geo-journal / forum-qa),
      thus stably triggering hits, races, and cascading termination;
    - Fill the rest with non-answer sources; when n exceeds the number of built-in sources, cycle and add a sequence number suffix.
    """
    if n < 1:
        raise ValueError("Number of parallel agents must be at least 1")
    if n == len(DEMO_SOURCES):
        return list(DEMO_SOURCES)

    answer_pool = [s for s in DEMO_SOURCES if s.holds_answer]
    filler_pool = [s for s in DEMO_SOURCES if not s.holds_answer]
    k_answer = min(len(answer_pool), 2 if n >= 2 else 1)
    n_filler = n - k_answer

    fillers: List[Source] = []
    seen: dict = {}
    for i in range(n_filler):
        base = filler_pool[i % len(filler_pool)]
        seen[base.name] = seen.get(base.name, 0) + 1
        name = base.name if seen[base.name] == 1 else f"{base.name}-{seen[base.name]}"
        fillers.append(Source(name, base.latency, base.content, False))

    sources = fillers
    # Insert the answer-containing sources at fixed positions (following the default layout: near the front but not at the very front, to facilitate observation of parallel progress)
    for j, src in enumerate(answer_pool[:k_answer]):
        pos = min(2 + 2 * j, len(sources))
        sources.insert(pos, Source(src.name, src.latency, src.content, src.holds_answer))
    return sources
