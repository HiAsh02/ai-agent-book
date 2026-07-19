"""
Experiment 3-13 Full Demo: Extracting Tacit Knowledge from Judicial Precedents.

Run:
    python demo.py

Execute four stages sequentially:
  Stage 1  Bottom-up Factor Discovery: Let the LLM freely summarize factors and merge them into a modular schema (core + extensions for each charge);
  Stage 2  Structured Extraction: Extract factors from each precedent using the discovered schema (with caching);
  Stage 3  Clustering + Hierarchical Importance: Cluster factor vectors into "case prototypes", compute global and within-prototype factor importance;
  Stage 4  Conversational Suggestion Agent: Match new case facts to the nearest prototype, ask for missing factors by importance, and give suggestions.
"""
import json
import os
import sys

import archetypes
import discovery
from advisor_agent import LegalAdvisorAgent
from extractor import extract_dataset, load_dataset


def section(title):
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def main():
    cases = load_dataset()

    # ---------- Stage 1: Bottom-up Factor Discovery ----------
    section("Stage 1 / Bottom-up Factor Discovery (LLM free induction → modular schema)")
    schema = discovery.discover_schema(cases, batch_size=12, use_cache=True)
    discovery.print_schema(schema)

    # ---------- Stage 2: Structured Extraction ----------
    section("Stage 2 / Structured Extraction (extract factors from each precedent using the discovered schema)")
    results = extract_dataset(schema, use_cache=True, verbose=True)
    print("\nExtraction samples (first 2):")
    for r in results[:2]:
        print(f"\n[{r['id']}] {r['fact'][:56]}...")
        print(f"  Extracted: {json.dumps(r['extracted'], ensure_ascii=False)}")

    # ---------- Stage 3: Clustering + Hierarchical Importance ----------
    section("Stage 3 / Clustering into Case Prototypes + Hierarchical Factor Importance")
    model = archetypes.fit(schema, results, save=True)
    archetypes.print_model(model)
    print(f"\n  Model saved -> {os.path.join('data', 'archetypes.json')}")

    # ---------- Stage 4: Conversational Sentencing Suggestion Agent ----------
    section("Stage 4 / Conversational Sentencing Suggestion Agent (match nearest prototype + ask by importance)")
    agent = LegalAdvisorAgent(schema, model)

    user_turn1 = (
        "My friend was previously sentenced for theft. This time he pried open the door of someone's house and stole things, and did not resist when caught."
        "How long would the sentence be in this situation?"
    )
    print(f"\nUser: {user_turn1}")
    known = agent.extract_known(user_turn1)
    print(f"\nAgent identified factors: {json.dumps(known, ensure_ascii=False)}")

    questions = agent.missing_important_questions(known)
    print("\nAgent asks (sorted by global factor importance, only missing and important ones):")
    for q in questions[:5]:
        print(f"  - [{q['name_cn']}  Importance{q['importance']:.3f}] {q['question']}")

    user_turn2 = (
        "To add: the stolen items are worth about 50,000 yuan, he did not return the stolen goods afterwards,"
        "did not carry a weapon during the crime, acted alone, and pleaded guilty in court."
    )
    print(f"\nUser: {user_turn2}")
    known2 = agent.extract_known(user_turn1 + " " + user_turn2)
    print(f"\nAgent updated factors: {json.dumps(known2, ensure_ascii=False)}")

    arch, advice = agent.advise(known2)
    print(f"\nAgent matched to Prototype#{arch['id']} (median typical sentence {arch['months']['median']:.0f} months)")
    print("\nAgent sentencing suggestion:\n")
    print(advice)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"Startup failed:{exc}", file=sys.stderr)
        sys.exit(1)


