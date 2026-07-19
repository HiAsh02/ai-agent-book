# -*- coding: utf-8 -*-
"""Information Visibility Audit.

This is the core tool of this experiment for "verifiable information access control": each time the judge delivers a piece of information to the context of one (or more) players, a record is registered here — which category the information belongs to, a summary of its content, and **whose context it entered**. After the game ends, printing this audit table provides objective proof of whether information isolation is correct (e.g., "werewolf teammate identity" only enters the werewolf's context, "seer investigation result" only enters the seer's own context, "public speech" enters everyone's context).
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class AuditRecord:
    round_no: int          # Round
    phase: str             # Phase (Night/Day/...)
    category: str          # Information Category (e.g., "Werewolf Teammate Identity", "Seer Investigation Result", "Public Speech")
    content: str           # Information Content Summary
    visible_to: List[str]  # Which players' contexts this information entered (list of player names)


@dataclass
class AuditLog:
    records: List[AuditRecord] = field(default_factory=list)

    def add(self, round_no, phase, category, content, visible_to):
        self.records.append(AuditRecord(round_no, phase, category, content, list(visible_to)))

    def print_table(self, all_players):
        """ Print the complete information visibility audit table."""
        print("\n" + "=" * 78)
        print("Information Visibility Audit Table (which players' contexts each piece of information entered)")
        print("=" * 78)
        header = f"{'Round':<4}{'Phase':<6}{'Category':<14}{'Visible Players':<20}Content"
        print(header)
        print("-" * 78)
        for r in self.records:
            vis = "All" if set(r.visible_to) == set(all_players) else "、".join(r.visible_to)
            content = r.content if len(r.content) <= 30 else r.content[:29] + "…"
            print(f"{r.round_no:<5}{r.phase:<7}{r.category:<15}{vis:<21}{content}")
        print("=" * 78)
