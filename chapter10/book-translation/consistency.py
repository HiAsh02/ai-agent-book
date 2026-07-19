"""
Terminology consistency checker.

Idea: For each English term of interest, pre-list its "several common but different" translations in Chinese.
Scan the translations of each chapter of the book, and count how many different translations actually appear for each term:
  - Only 1 appears → consistent throughout the book;
  - >= 2 appear → terminology drift (inconsistent).

This is not scoring the model, but using deterministic string matching to objectively measure "whether the same term is unified throughout the book."
"""

#  Each term: canonical is the recommended/glossary-specified translation; variants are several "mutually different" common translations.
#  Note: variants should try not to be substrings of each other to avoid double counting (e.g., "嵌入向量" is grouped under the "嵌入" family).
TRACKED_TERMS = [
    {"en": "token",       "canonical": "token",  "variants": ["token", "token", "token", "token"]},
    {"en": "embedding",   "canonical": "embedding",  "variants": ["embedding", "word vector", "vector representation"]},
    {"en": "prompt",      "canonical": "prompt", "variants": ["prompt", "prompt", "prompt"]},
    {"en": "inference",   "canonical": "inference",  "variants": ["inference", "inference"]},
    {"en": "latency",     "canonical": "latency",  "variants": ["latency", "latency", "latency"]},
    {"en": "attention",   "canonical": "attention", "variants": ["attention", "attention"]},
    {"en": "transformer", "canonical": "Transformer", "variants": ["Transformer", "transformer", "transformer"]},
    {"en": "throughput",  "canonical": "throughput", "variants": ["throughput", "throughput", "throughput"]},
    {"en": "fine-tuning", "canonical": "fine-tuning",  "variants": ["fine-tuning", "fine-tuning"]},
]


import re


def _strip_code(text):
    """Remove fence code blocks and inline code: code should remain in English as per translation guidelines and should not be counted in terminology consistency statistics."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    return text


#  The editorial department's "house style": specify a clear translation for several terms that differs from the model's default translation.
#  These translations are all legitimate and more precise choices, used to examine "whether a shared glossary can enforce the specified translations throughout the book."
#   mandated: glossary-specified translation; default: the common default translation used when the model translates freely.
MANDATED_TERMS = [
    {"en": "token",     "mandated": "token",   "default": "token"},
    {"en": "prompt",    "mandated": "prompt", "default": "prompt"},
    {"en": "latency",   "mandated": "latency",   "default": "latency"},
    {"en": "embedding", "mandated": "embedding vector", "default": "embedding"},
]


def check_adherence(translations):
    """
    Glossary compliance rate: For each "specified term", count how many chapters
    that contain the concept use the glossary-specified translation (rather than the default translation).

    This is the core value of the manager mode: a shared glossary enforces the specified translation across all chapters;
    a single agent cannot see the glossary and can only use its own default translation.
    """
    rows = []
    hit_total = 0
    concept_total = 0
    for t in MANDATED_TERMS:
        m, d = t["mandated"], t["default"]
        chapters_with_concept = 0
        chapters_adhered = 0
        for name, raw in translations.items():
            text = _strip_code(raw)
            has_m = m in text
            # If default is a substring of mandated (e.g., "embedding" is a substring of "embedding vector"), remove mandated before checking
            has_d = (d in text.replace(m, "")) if d in m else (d in text)
            if has_m or has_d:
                chapters_with_concept += 1
                if has_m:
                    chapters_adhered += 1
        if chapters_with_concept:
            concept_total += chapters_with_concept
            hit_total += chapters_adhered
            rows.append({
                "en": t["en"], "mandated": m, "default": d,
                "adhered": chapters_adhered, "total": chapters_with_concept,
            })
    rate = hit_total / concept_total if concept_total else 1.0
    return {"rows": rows, "rate": rate}


def _variant_in_chapter(text, variant, other_variants):
    """
    Determine whether a certain variant appears "independently" in the text.
    For cases like "prompt" which can be a substring of "prompt word"/"prompt phrase": only count if it still appears after removing longer variants.
    """
    longer = [v for v in other_variants if variant in v and v != variant]
    if not longer:
        return variant in text
    tmp = text
    for v in longer:
        tmp = tmp.replace(v, "")
    return variant in tmp


def analyze(translations):
    """
    translations: {chapter_name: translated text}
    Returns:
      results: analysis for each term (which translations are used, consistency, usage per chapter)
      consistent_terms / total_terms / rate
    """
    results = []
    consistent = 0
    total = 0
    for term in TRACKED_TERMS:
        variants = term["variants"]
        used = {}  # variant -> [chapters where this translation appears]
        for name, raw in translations.items():
            text = _strip_code(raw)
            for v in variants:
                others = [x for x in variants if x != v]
                if _variant_in_chapter(text, v, others):
                    used.setdefault(v, []).append(name)
        if not used:
            # The term does not appear anywhere in the book; skip statistics
            continue
        total += 1
        distinct = list(used.keys())
        is_consistent = len(distinct) == 1
        if is_consistent:
            consistent += 1
        results.append(
            {
                "en": term["en"],
                "canonical": term["canonical"],
                "distinct_used": distinct,
                "consistent": is_consistent,
                "by_variant": used,
            }
        )
    rate = consistent / total if total else 1.0
    return {
        "results": results,
        "consistent_terms": consistent,
        "total_terms": total,
        "rate": rate,
    }
