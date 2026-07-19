"""
Phase 2: Structured Extraction — Extract structured factors from judgment texts using the discovered schema.

Process:
  1. First determine the charge of the case (select from known charges in the schema);
  2. Extract factors item by item according to "core general factors + extended factors for this charge", output structured JSON;
  3. Factors not mentioned in the text return null (for the dialogue Agent to determine "what information is missing");
  4. With disk cache (data/extracted.jsonl), re-running after a one-time extraction is almost free.

Output is uniformly {"charge": <charge>, <factor_key>: <value|null>, ...}.
"""
import json
import os

from config import MODEL, get_client
from discovery import factors_for_charge, load_schema

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_PATH = os.path.join(DATA_DIR, "extracted.jsonl")


def _factor_lines(factors):
    lines = []
    for f in factors:
        if f["kind"] == "numeric":
            t = "Number (integer, remove unit)"
        elif f["kind"] == "bool":
            t = "true/false"
        else:
            t = "One of the values:" + "/".join(f.get("values", [])) if f.get("values") else "Categorical value"
        lines.append(f'  - "{f["key"]}": {t}  # {f["name_cn"]}')
    return "\n".join(lines)


def _charges(schema):
    return list(schema.get("extensions", {}).keys())


def extract_one(fact_text, schema=None, client=None, charge=None):
    """Extract {charge, factors...} from a single judgment text. Missing factors take null.

    When charge is known (dataset extraction), reuse it directly to save one call; when unknown (new case in dialogue), first let LLM determine it.
    """
    schema = schema or load_schema()
    client = client or get_client()
    charges = _charges(schema)

    #  Step 1: Determine charge (call LLM only if not provided)
    if charge is None:
        charge_resp = client.chat.completions.create(
            model=MODEL, temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content":
                    "Determine which charge the following criminal case belongs to, only from these options:"
                    + "/".join(charges) + '. Output only JSON: {"charge": "..."}.'},
                {"role": "user", "content": fact_text},
            ],
        )
        charge = json.loads(charge_resp.choices[0].message.content).get("charge")
    if charge not in charges:  #  Fallback: default to the first charge
        charge = charges[0]

    #  Step 2: Extract factors applicable to this charge
    factors = factors_for_charge(schema, charge)
    sys = (
        "You are an information extraction assistant for judicial data analysis. Please extract the following factors from the \"facts\" paragraph of the judgment:"
        "Output only a JSON object:\n" + _factor_lines(factors) + "\n\nRules:\n"
        "1. Numeric factors: output integer (remove '元', '人民币', '名', etc.).\n"
        "2. Boolean factors: true if text explicitly supports, false if explicitly denies.\n"
        "3. Categorical factors: only take one of the given values.\n"
        "4. Factors with no relevant information in the text: return null (do not guess).\n"
        "5. Output only JSON, no explanation."
    )
    resp = client.chat.completions.create(
        model=MODEL, temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": sys},
                  {"role": "user", "content": f"Facts paragraph of the judgment:\n{fact_text}"}],
    )
    raw = json.loads(resp.choices[0].message.content)
    return _normalize(raw, charge, factors)


def _normalize(raw, charge, factors):
    out = {"charge": charge}
    for f in factors:
        v = raw.get(f["key"])
        if v is None or v == "":
            out[f["key"]] = None
        elif f["kind"] == "numeric":
            if isinstance(v, str):
                digits = "".join(ch for ch in v if ch.isdigit())
                out[f["key"]] = int(digits) if digits else None
            else:
                out[f["key"]] = int(v)
        elif f["kind"] == "bool":
            out[f["key"]] = bool(v) if isinstance(v, bool) else str(v).lower() in ("true", "1", "Yes")
        else:  # categorical
            out[f["key"]] = str(v)
    return out


def load_dataset():
    path = os.path.join(DATA_DIR, "cases.jsonl")
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def extract_dataset(schema, use_cache=True, verbose=True):
    """Extract for the entire dataset with caching. Returns a list, each item contains original case fields + `extracted`."""
    cases = load_dataset()
    cache = {}
    if use_cache and os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    cache[rec["id"]] = rec["extracted"]

    client = get_client()
    results, n_called = [], 0
    for c in cases:
        if c["id"] in cache:
            extracted = cache[c["id"]]
        else:
            extracted = extract_one(c["fact"], schema=schema, client=client,
                                    charge=c.get("charge"))
            cache[c["id"]] = extracted
            n_called += 1
            if verbose:
                print(f"  Extracting {c['id']} ({extracted.get('charge')}) ... done")
        results.append({**c, "extracted": extracted})

    with open(CACHE_PATH, "w", encoding="utf-8") as fh:
        for r in results:
            fh.write(json.dumps({"id": r["id"], "extracted": r["extracted"]},
                                ensure_ascii=False) + "\n")
    if verbose:
        print(f"  Actual LLM calls this time: {n_called} times, the rest hit cache.")
    return results
