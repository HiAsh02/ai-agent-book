"""
Phase 1: Bottom-up factor discovery.

Instead of predefining any rigid data schema:
  1. Feed batches of judgment texts to an LLM, letting it **freely list** all factors that may affect the verdict in each batch;
  2. Aggregate the raw factors discovered from all batches, then use one more LLM call to **merge and normalize** them, producing a
     「modular data schema」:
        - core        —— generic factors applicable to all charges (voluntary surrender, compensation, guilty plea, prior record...);
        - extensions  —— charge-specific factors (theft→amount involved/breaking into premises; injury→injury level...).

The resulting schema is saved to data/schema.json for reuse in subsequent extraction/clustering/dialogue steps.
Each factor in the schema includes: key (English), name_cn, kind (numeric/bool/categorical),
values (categorical values), direction (aggravating/mitigating/neutral), question (guiding follow-up question).
"""
import json
import os

from config import MODEL, get_client

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SCHEMA_PATH = os.path.join(DATA_DIR, "schema.json")

_BATCH_SYS = """You are an expert assisting judicial data analysis. Below are several "facts" paragraphs from criminal judgments.
Please **freely summarize** all factors that may affect the court's sentencing/verdict (do not limit yourself to any preset list).
For each factor, provide:
  - key: short English snake_case identifier
  - name_cn: Chinese name
  - charge: the charge to which this factor mainly applies (fill "通用" if applicable to all types)
  - kind: numeric (numerical, e.g., amount/number) | bool (yes/no circumstance) | categorical (multiple values, e.g., injury level)
  - values: if kind is categorical, list the observed value array; otherwise empty array
Output only JSON: {"factors": [ {factor...}, ... ]}"""

_CONSOLIDATE_SYS = """You are a judicial data modeling expert. Below are **raw factor lists** discovered separately from multiple judgment examples
(they may contain duplicates, synonyms, inconsistent naming). Please **merge, deduplicate, and normalize** them into a modular data schema:
  - core: generic factors applicable to all charges (e.g., voluntary surrender, compensation and forgiveness, guilty plea and acceptance of punishment, prior record and recidivism)
  - extensions: an object whose keys are charge names (e.g., "盗窃罪"/"故意伤害罪"/"诈骗罪") and values are arrays of factors specific to that charge
Normalization requirements:
  - Merge synonymous factors (e.g., "自首/主动投案", "认罪认罚/认罪/如实供述", "赔偿/退赔/退赃",
    "累犯/前科", "涉案金额/物品价值/诈骗金额" under the same charge keep only one),
    keep only the clearest key and Chinese name per group;
  - Remove factors with no substantive relation to sentencing (e.g., descriptive information like defendant's gender, crime scene);
  - Do not redundantly keep factors that are opposites of each other, such as "是否否认指控/辩称正当防卫" and "认罪认罚".
Each factor output fields:
  key, name_cn, kind (numeric|bool|categorical), values (array of categorical values, otherwise []),
  direction (aggravating | mitigating | neutral),
  question (a Chinese guiding question to ask the party when this factor is missing)
Output only JSON: {"core": [...], "extensions": {"charge": [...], ...}}"""


def _chat_json(client, system, user):
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )
    return json.loads(resp.choices[0].message.content)


def discover_schema(cases, batch_size=12, use_cache=True, verbose=True):
    """Bottom-up factor discovery and merging into a modular schema. With disk cache (to avoid repeated costs)."""
    if use_cache and os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, encoding="utf-8") as fh:
            if verbose:
                print(f"  Cache hit schema -> {SCHEMA_PATH}")
            return json.load(fh)

    client = get_client()

    # --- Step 1: Batch free discovery ---
    raw_factors = []
    for start in range(0, len(cases), batch_size):
        batch = cases[start:start + batch_size]
        facts = "\n\n".join(f"[Case{start + j + 1}]（{c['charge']}）{c['fact']}"
                            for j, c in enumerate(batch))
        out = _chat_json(client, _BATCH_SYS, facts)
        got = out.get("factors", [])
        raw_factors.extend(got)
        if verbose:
            print(f"  Batch {start // batch_size + 1} : discovered {len(got)} candidate factors")

    # --- Step 2: Merge / normalize into modular schema ---
    if verbose:
        print(f"  Aggregated {len(raw_factors)} raw factors, merging and normalizing ...")
    schema = _chat_json(client, _CONSOLIDATE_SYS,
                        "Raw factor list: \n" + json.dumps(raw_factors, ensure_ascii=False))
    schema.setdefault("core", [])
    schema.setdefault("extensions", {})

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SCHEMA_PATH, "w", encoding="utf-8") as fh:
        json.dump(schema, fh, ensure_ascii=False, indent=2)
    if verbose:
        print(f"  Discovered modular schema saved -> {SCHEMA_PATH}")
    return schema


# --- Schema quick access ---------------------------------------------------------
def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def factors_for_charge(schema, charge):
    """Return the list of factors applicable to a given charge: core generic factors + charge-specific extension factors (deduplicated by key)."""
    seen, out = set(), []
    for f in schema.get("core", []) + schema.get("extensions", {}).get(charge, []):
        if f["key"] in seen:  #  Deduplication: if a factor appears in both core and extensions, keep only once
            continue
        seen.add(f["key"])
        out.append(f)
    return out


def all_factors(schema):
    """All factors (core + all extensions), deduplicated by key."""
    seen, out = set(), []
    lists = [schema.get("core", [])] + list(schema.get("extensions", {}).values())
    for lst in lists:
        for f in lst:
            if f["key"] in seen:
                continue
            seen.add(f["key"])
            out.append(f)
    return out


def print_schema(schema):
    print("  Core generic factors (core):")
    for f in schema.get("core", []):
        vals = f"={f['values']}" if f.get("values") else ""
        print(f"    - {f['key']:<16} {f['name_cn']}  [{f['kind']}{vals}] {f.get('direction','')}")
    for charge, lst in schema.get("extensions", {}).items():
        print(f"  Extension factors · {charge}:")
        for f in lst:
            vals = f"={f['values']}" if f.get("values") else ""
            print(f"    - {f['key']:<16} {f['name_cn']}  [{f['kind']}{vals}] {f.get('direction','')}")
