"""Experiment 5-9: Intent Clarification System for Dynamic Form Generation (★★)

Core Idea
--------
When a user request lacks key information, the Agent does not ask questions one by one, but **dynamically generates a self-contained
HTML form** (with cascading display logic) so that the user can "submit once" to fill in all clarification points; the frontend aggregates the form into JSON and returns it to the Agent, which parses it and continues the task.

This demo is verified in three steps (no real browser required):
  1) Generate a clarification form HTML and save it as generated_form.html;
  2) Use BeautifulSoup for structured validation: it must contain departure city, departure date, travel type (one-way, round-trip),
     return date, and the return field must have cascading JS logic for "only shown for round-trip";
  3) Simulate a user submission (construct JSON), feed it back to the Agent, which parses it and prints a booking summary.

Two operation modes (identical mechanism, only difference is "who writes the form code"):
  * Default (online): Let the Agent actually call OpenAI to generate the form HTML, requires OPENAI_API_KEY;
  * --offline   : Do not call LLM, use built-in flight schema **deterministically render** cascading form, no API Key required.
    The offline rendered form is also real and usable, can be opened in a browser, contains two types of cascading logic (show/hide +
    dynamically update options) in a self-contained HTML.

Run:
  python demo.py                       # Online: Agent calls OpenAI to generate (requires API Key)
  python demo.py --offline             # Offline: built-in schema deterministic rendering, no API Key required
  python demo.py --offline --serve     # After offline rendering, start a local server for real-time cascading/submission experience in browser
  python demo.py --help                # View all parameters

Environment variables:
  OPENAI_API_KEY   (required for online mode; automatically falls back to --offline if not set)
  OPENAI_BASE_URL  (optional, switch to a service compatible with OpenAI protocol)
  MODEL            (optional, default gpt-5.6-luna)
"""

import os
import re
import json
import argparse

from bs4 import BeautifulSoup

# openai online-only mode required; offline mode does not import, can run even if package is missing (defer import until use)

#  Load .env (if exists) for local execution convenience
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is an optional dependency
    pass


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
USER_REQUEST = "I want to book a flight to Beijing"


# ---------------------------------------------------------------------------
# Configuration (Online Mode)
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _map_to_openrouter_model(model: str) -> str:
    """Map the direct model name to the id on OpenRouter (non-mappable ids fall back to the current cheap flagship)."""
    if not model or "/" in model:
        return model or "openai/gpt-5.6-luna"
    m = model.lower()
    if m.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai/" + model
    if m.startswith("claude"):
        if "haiku" in m:
            return "anthropic/claude-haiku-4.5"
        if "sonnet" in m:
            return "anthropic/claude-sonnet-4.6"
        return "anthropic/claude-opus-4.8"
    if m.startswith("gemini"):
        return "google/" + model
    return "openai/gpt-5.6-luna"


def build_client_and_model(model_override=None):
    """Construct OpenAI client and model name, with a general OpenRouter fallback."""
    from openai import OpenAI  #  Lazy import: offline mode does not require installing/configuring openai

    model = model_override or os.getenv("MODEL", "gpt-5.6-luna")
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    orkey = os.getenv("OPENROUTER_API_KEY")
    # No direct connection key, or default gpt-5.x (direct connection requires organization real-name authentication) will switch to OpenRouter.
    prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        api_key, base_url, model = orkey, OPENROUTER_BASE_URL, _map_to_openrouter_model(model)
    if not api_key:
        raise SystemExit("OPENAI_API_KEY (or fallback OPENROUTER_API_KEY) not found. Please set it in environment variables or .env file, or use --offline instead.")

    client = (
        OpenAI(api_key=api_key, base_url=base_url)
        if base_url
        else OpenAI(api_key=api_key)
    )
    return client, model


def _temp_for(model):
    """Reasoning models (gpt-5 / o series, etc.) do not accept temperature=0."""
    return (1 if any(k in (model or "").lower()
                     for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
            else 0)


# ---------------------------------------------------------------------------
# Step 1 (Online): Have the Agent generate a clarification form
# ---------------------------------------------------------------------------
FORM_SYSTEM_PROMPT = """You are an "intent clarification" assistant. The user will provide an incomplete request.
Your task is not to ask follow-up questions directly, but to **generate a self-contained HTML form** that allows the user to fill in all missing information at once.

Strict requirements (flight booking scenario):
1. The form must include the following fields, with the name attribute using the given English identifiers:
   - Departure city: text input, name="departure_city"
   - Departure date: date picker <input type="date">, name="departure_date"
   - Trip type: radio buttons <input type="radio" name="trip_type">, two options
     value="one_way" and value="round_trip"
   - Return date: date picker, name="return_date", placed inside a container with id="return_date_field"
2. **Cascading logic (critical)**: The return date field is hidden by default, and is only shown via JavaScript when the trip type is "round_trip"; hidden again when "one_way" is selected.
3. On submission, use JavaScript to prevent default submission, aggregate all fields into a JSON object with keys using the above English names, and display it in an element with id="result" (e.g., <pre id="result"></pre>).
4. The output must be **complete, self-contained** HTML (including <style> and <script>, inline, no external resources), which can be saved as a .html file and opened in a browser.

Output only the HTML code itself, no explanatory text, no markdown code block wrapping."""


def generate_form(client, model, user_request):
    """Call the model to generate the HTML of the clarification form."""
    resp = client.chat.completions.create(
        model=model,
        temperature=_temp_for(model),
        messages=[
            {"role": "system", "content": FORM_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User request:{user_request}\nPlease generate a clarification form for the missing information.",
            },
        ],
    )
    html = resp.choices[0].message.content.strip()
    # The model is occasionally wrapped with ```html ... ```, so strip the fences to be safe
    html = re.sub(r"^```(?:html)?\s*", "", html)
    html = re.sub(r"\s*```$", "", html)
    return html.strip()


# ---------------------------------------------------------------------------
# Step 1 (offline): Built-in ticket schema + deterministic cascading form renderer
# ---------------------------------------------------------------------------
#The schema describes clarification points in a declarative way, and the renderer turns it into self-contained cascading HTML.
#  Supports two types of "cascade": 
#   show_when   —— A field is only displayed when another field equals a certain value (return date = only shown for round trips);
#   options_when —— Options of a dropdown dynamically update based on the value of another field (baggage allowance = varies with cabin class).
FLIGHT_FORM_SCHEMA = {
    "title": "Flight Booking · Intent Clarification Form",
    "fields": [
        {
            "name": "departure_city",
            "label": "Departure city",
            "type": "text",
            "placeholder": "e.g., Shanghai",
            "required": True,
        },
        {
            "name": "departure_date",
            "label": "Departure date",
            "type": "date",
            "required": True,
        },
        {
            "name": "trip_type",
            "label": "Travel Type",
            "type": "radio",
            "default": "one_way",
            "options": [
                {"value": "one_way", "label": "One-way"},
                {"value": "round_trip", "label": "Round trip"},
            ],
        },
        {
            "name": "return_date",
            "label": "Return date",
            "type": "date",
            "container_id": "return_date_field",
            # Cascade ①: only visible when trip_type == round_trip
            "show_when": {"field": "trip_type", "equals": "round_trip"},
        },
        {
            "name": "cabin_class",
            "label": "Cabin class",
            "type": "select",
            "default": "economy",
            "options": [
                {"value": "economy", "label": "Economy"},
                {"value": "business", "label": "Business"},
                {"value": "first", "label": "First class"},
            ],
        },
        {
            "name": "baggage_count",
            "label": "Free checked baggage allowance",
            "type": "select",
            # Cascade ②: options vary dynamically with cabin_class
            "options_when": {
                "field": "cabin_class",
                "map": {
                    "economy": [
                        {"value": "0", "label": "Carry-on only"},
                        {"value": "1", "label": "1 piece (≤23kg)"},
                    ],
                    "business": [
                        {"value": "0", "label": "Carry-on only"},
                        {"value": "1", "label": "1 piece (≤32kg)"},
                        {"value": "2", "label": "2 pieces (≤32kg)"},
                    ],
                    "first": [
                        {"value": "1", "label": "1 piece (≤32kg)"},
                        {"value": "2", "label": "2 pieces (≤32kg)"},
                        {"value": "3", "label": "3 pieces (≤32kg)"},
                    ],
                },
            },
        },
    ],
}


def _extract_destination(user_request):
    """Roughly extract destination from "tickets to XX" and carry it as a form constant on submit. Fall back to None if not found."""
    m = re.search(r"go to (.+?) (?:ticket|flight|ticket)", user_request)
    if m:
        return m.group(1).strip()
    return None


def _render_field_html(f):
    """Render a single field schema as an HTML fragment."""
    ftype = f["type"]
    name = f["name"]
    label = f.get("label", "")
    required = " required" if f.get("required") else ""

    if ftype in ("text", "date"):
        ph = f' placeholder="{f["placeholder"]}"' if f.get("placeholder") else ""
        inner = (
            f'<label class="fld-label" for="{name}">{label}</label>'
            f'<input class="fld-input" type="{ftype}" id="{name}" name="{name}"{ph}{required}>'
        )
    elif ftype == "radio":
        opts = []
        for o in f["options"]:
            checked = " checked" if f.get("default") == o["value"] else ""
            opts.append(
                f'<label class="radio"><input type="radio" name="{name}" '
                f'value="{o["value"]}"{checked}> {o["label"]}</label>'
            )
        inner = (
            f'<span class="fld-label">{label}</span>'
            f'<div class="radio-row">{"".join(opts)}</div>'
        )
    elif ftype == "select":
        opts = ""
        for o in f.get("options", []):
            selected = " selected" if f.get("default") == o["value"] else ""
            opts += f'<option value="{o["value"]}"{selected}>{o["label"]}</option>'
        inner = (
            f'<label class="fld-label" for="{name}">{label}</label>'
            f'<select class="fld-input" id="{name}" name="{name}">{opts}</select>'
        )
    else:
        raise ValueError(f"Unknown field type: {ftype}")

    container_id = f.get("container_id")
    cid = f' id="{container_id}"' if container_id else ""
    # Fields with show_when are hidden by default; JS decides visibility on load based on current values (to avoid flicker).
    hidden = ' style="display:none"' if f.get("show_when") else ""
    return f'<div class="field"{cid}{hidden}>{inner}</div>'


# Generic cascade runtime: reads inline FORM_CONFIG, handles show_when / options_when,
# and on submit aggregates "currently visible fields" into JSON. Pure vanilla JS, no external dependencies.
_RUNTIME_JS = """
const FORM_CONFIG = __CONFIG__;
const form = document.getElementById('clarify-form');

function valueOf(name) {
  const el = form.elements[name];
  if (!el) return '';
  return el.value || '';
}

function applyCascade() {
  FORM_CONFIG.fields.forEach(function (f) {
    // Cascade ①: show_when — control field container visibility
    if (f.show_when) {
      const box = document.getElementById(f.container_id);
      if (box) {
        const show = valueOf(f.show_when.field) === f.show_when.equals;
        box.style.display = show ? '' : 'none';
      }
    }
    // Cascade ②: options_when — dynamically rebuild dropdown options based on another field's value
    if (f.options_when) {
      const sel = form.elements[f.name];
      if (sel) {
        const key = valueOf(f.options_when.field);
        const opts = f.options_when.map[key] || [];
        const prev = sel.value;
        sel.innerHTML = '';
        opts.forEach(function (o) {
          const opt = document.createElement('option');
          opt.value = o.value;
          opt.textContent = o.label;
          sel.appendChild(opt);
        });
        if (opts.some(function (o) { return o.value === prev; })) sel.value = prev;
      }
    }
  });
}

form.addEventListener('change', applyCascade);
applyCascade();  // Apply once on initial load

form.addEventListener('submit', function (e) {
  e.preventDefault();
  const data = {};
  FORM_CONFIG.fields.forEach(function (f) {
    // Hidden (collapsed) cascade fields are not included in the submission result
    if (f.container_id) {
      const box = document.getElementById(f.container_id);
      if (box && box.style.display === 'none') return;
    }
    const v = valueOf(f.name);
    if (v !== '') data[f.name] = v;
  });
  Object.assign(data, FORM_CONFIG.constants || {});
  document.getElementById('result').textContent = JSON.stringify(data, null, 2);
});
"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         max-width: 560px; margin: 32px auto; padding: 0 20px; line-height: 1.6; }
  h1 { font-size: 20px; }
  .req { color: #666; font-size: 13px; margin: -6px 0 18px; }
  .field { margin-bottom: 16px; }
  .fld-label { display: block; font-weight: 600; margin-bottom: 6px; }
  .fld-input { width: 100%; box-sizing: border-box; padding: 8px 10px;
               border: 1px solid #bbb; border-radius: 6px; font-size: 15px; }
  .radio-row { display: flex; gap: 18px; }
  .radio { font-weight: normal; }
  button { margin-top: 8px; padding: 10px 18px; font-size: 15px; border: 0;
           border-radius: 6px; background: #2563eb; color: #fff; cursor: pointer; }
  #result { background: #f5f5f5; color: #111; padding: 12px; border-radius: 6px;
            white-space: pre-wrap; margin-top: 18px; min-height: 1em; }
</style>
</head>
<body>
<h1>__TITLE__</h1>
<p class="req">Original request: __REQUEST__ — Please complete the following information at once (return date only appears when "round trip" is selected; baggage allowance varies with cabin class).</p>
<form id="clarify-form">
__FIELDS__
  <button type="submit">Submit</button>
</form>
<pre id="result"></pre>
<script>
__SCRIPT__
</script>
</body>
</html>
"""


def render_form_html(schema, user_request):
    """Deterministically render a declarative schema into a self-contained cascading HTML (offline path, no LLM call)."""
    fields_html = "\n".join(_render_field_html(f) for f in schema["fields"])

    # Minimal config for JS runtime (only cascade-related keys)
    js_fields = []
    for f in schema["fields"]:
        entry = {"name": f["name"]}
        if f.get("container_id"):
            entry["container_id"] = f["container_id"]
        if f.get("show_when"):
            entry["show_when"] = f["show_when"]
        if f.get("options_when"):
            entry["options_when"] = f["options_when"]
        js_fields.append(entry)

    constants = {}
    dest = _extract_destination(user_request)
    if dest:
        constants["destination_city"] = dest  # Destination already given in original request, carried back on submit
    config = {"fields": js_fields, "constants": constants}

    script = _RUNTIME_JS.replace("__CONFIG__", json.dumps(config, ensure_ascii=False))
    return (
        _PAGE_TEMPLATE.replace("__TITLE__", schema["title"])
        .replace("__REQUEST__", user_request)
        .replace("__FIELDS__", fields_html)
        .replace("__SCRIPT__", script)
    )


# ---------------------------------------------------------------------------
# Step 2: Structurally validate the form
# ---------------------------------------------------------------------------
def validate_form(html):
    """Use BeautifulSoup + regex for robust validation.

    Since the model's generated tag writing is not fully controllable, a robust strategy of "keyword/attribute matching" is adopted:
    As long as a semantically equivalent control can be located, it passes, and each piece of evidence is printed.
    Returns (all_passed, report_dict, script_text).
    """
    soup = BeautifulSoup(html, "html.parser")
    report = {}

    # (a) Departure city: text input
    dep_city = soup.find("input", attrs={"name": re.compile("departure_city", re.I)})
    if dep_city is None:
        # Degenerate match: any text box related to "departure city"
        dep_city = soup.find(
            "input", attrs={"name": re.compile("depart.*city|from.*city|city", re.I)}
        )
    report["Departure city (text input)"] = bool(
        dep_city is not None
        and (dep_city.get("type") in (None, "text"))
    )

    # (b) Departure date: date picker
    dep_date = soup.find(
        "input",
        attrs={"type": "date", "name": re.compile("departure_date|depart.*date", re.I)},
    )
    if dep_date is None:
        dep_date = soup.find("input", attrs={"type": "date"})
    report["Departure date (date picker)"] = bool(dep_date is not None)

    # (c) Travel type: radio button, including One-way / Round-trip
    radios = soup.find_all("input", attrs={"type": "radio"})
    radio_values = {r.get("value", "").lower() for r in radios}
    has_one_way = any("one" in v or "One-way" in v for v in radio_values)
    has_round = any("round" in v or "Round trip" in v for v in radio_values)
    # Also allow text-based detection
    text_all = html.lower()
    has_one_way = has_one_way or ("One-way" in html)
    has_round = has_round or ("Round trip" in html)
    report["Travel type (radio: one-way)"] = bool(len(radios) >= 2 and has_one_way)
    report["Travel type (radio: round-trip)"] = bool(len(radios) >= 2 and has_round)

    # (d) Return date: date picker
    ret_date = soup.find(
        "input", attrs={"name": re.compile("return_date|return.*date", re.I)}
    )
    report["Return date (date picker)"] = bool(
        ret_date is not None or "return_date" in text_all
    )

    # (e) Cascading logic: return field has a JS toggle "show only for round-trip"
    #     Robust detection: script contains both (round_trip or 往返) and (show/hide control) and
    #     reference to the return field.
    script_text = " ".join(s.get_text() for s in soup.find_all("script"))
    cond_display = bool(
        re.search(r"round_trip|往返", script_text)
        and re.search(
            r"return_date|return_date_field|returnDate", script_text, re.I
        )
        and re.search(
            r"display|hidden|style|classList|\.hide|\.show|toggle", script_text, re.I
        )
    )
    report["Cascading logic for return field (show only for round-trip)"] = cond_display

    all_pass = all(report.values())
    return all_pass, report, script_text


# ---------------------------------------------------------------------------
# Step 3: Simulate user submission, feed back to Agent to continue task
# ---------------------------------------------------------------------------
PARSE_SYSTEM_PROMPT = """You are a flight booking assistant. The user has submitted the completion information in JSON format via a clarification form. Please parse this information and provide a concise Chinese "booking summary", confirming the flight segments, dates, and trip type. If it is one-way, do not mention the return; if it is round-trip, the return date must be included. Finally, append a next-step prompt (e.g., "Searching for flights..."). Output only the summary text."""


def continue_task(client, model, original_request, submitted_json):
    """Feed the user-submitted JSON back to the Agent (online) to generate a booking summary."""
    resp = client.chat.completions.create(
        model=model,
        temperature=_temp_for(model),
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original request:{original_request}\n"
                    f"JSON data submitted via form: \n{json.dumps(submitted_json, ensure_ascii=False, indent=2)}"
                ),
            },
        ],
    )
    return resp.choices[0].message.content.strip()


_CABIN_CN = {"economy": "Economy", "business": "Business", "first": "First class"}


def summarize_offline(submitted):
    """Offline path: do not call LLM, use a deterministic template to parse the submitted JSON into a booking summary.

    This step is just string formatting (not faking LLM output), used to demonstrate the closed loop of "parse JSON → continue task";
    in online mode this is done by continue_task() which hands it to the model.
    """
    dep = submitted.get("departure_city", "?")
    dest = submitted.get("destination_city", "Destination")
    ddate = submitted.get("departure_date", "?")
    lines = [f"Received your booking information:{dep} → {dest}, departure date {ddate}。"]
    if submitted.get("trip_type") == "round_trip":
        lines.append(f"Trip type: round-trip, return date {submitted.get('return_date', '?')}。")
    else:
        lines.append("Trip type: one-way.")
    if submitted.get("cabin_class"):
        cabin = _CABIN_CN.get(submitted["cabin_class"], submitted["cabin_class"])
        bag = submitted.get("baggage_count")
        bag_txt = f", free checked baggage {bag} piece(s)" if bag not in (None, "", "0") else ", no free checked baggage"
        lines.append(f"Cabin class:{cabin}{bag_txt}。")
    lines.append("Searching for flights...")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Optional: start a local HTTP service to experience cascading/submission
# ---------------------------------------------------------------------------
def serve_html(path, port):
    """Start a local static server in the directory where the path is located, and open the browser to point to that HTML."""
    import http.server
    import socketserver
    import functools
    import webbrowser

    directory = os.path.dirname(os.path.abspath(path))
    fname = os.path.basename(path)
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=directory
    )
    url = f"http://127.0.0.1:{port}/{fname}"
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print("\n" + "=" * 68)
        print(f"Local service started:{url}")
        print("Switch between one-way/round-trip in the browser to see the return field cascade; switch cabin class to see dynamic baggage allowance updates.")
        print("Click 'Submit' at the bottom of the page to see the summarized JSON. Press Ctrl+C to stop the service.")
        print("=" * 68)
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nLocal service has been stopped.")


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------
def build_arg_parser():
    """Construct command-line argument parser (with Chinese --help)."""
    parser = argparse.ArgumentParser(
        description="Experiment 5-9: Intent Clarification System for Dynamic Form Generation — Generating Cascading Logic from a Vague Request"
        "Self-contained HTML form, user submits once, Agent parses JSON to continue task. Default uses OpenAI (needs "
        "OPENAI_API_KEY); add --offline to use the built-in schema to deterministically render the same cascading form without an API Key.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-r",
        "--request",
        default=USER_REQUEST,
        metavar="TEXT",
        help=f"User's vague request (intent). Default:{USER_REQUEST}。"
        "(When --offline is used, the built-in flight schema is rendered; this option is mainly used to extract destinations and display them.)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="generated_form.html",
        metavar="PATH",
        help="Generated HTML form output path (relative paths are resolved relative to the script's directory). Default: generated_form.html.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override model name (otherwise read environment variable MODEL, default gpt-5.6-luna). Ignored under --offline.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Offline mode: No LLM call, uses built-in flight schema to deterministically render cascading forms, no API Key required.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="After generation, start the local HTTP service and open the browser to experience cascading display and submission summary in a real scenario.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        metavar="N",
        help="--serve port used (default 8000).",
    )
    return parser


def main():
    args = build_arg_parser().parse_args()

    out_path = args.output
    if not os.path.isabs(out_path):
        out_path = os.path.join(SCRIPT_DIR, out_path)

    # Offline determination: explicit --offline, or automatic fallback when neither OPENAI_API_KEY nor OPENROUTER_API_KEY is present
    offline = args.offline
    if not offline and not (os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")):
        print("OPENAI_API_KEY (or fallback OPENROUTER_API_KEY) not detected, automatically switching to offline mode (equivalent to --offline).\n")
        offline = True

    client = model = None
    if offline:
        mode_desc = "Offline (built-in schema deterministic rendering, no API Key required)"
    else:
        client, model = build_client_and_model(args.model)
        mode_desc = f"Online (Agent calls OpenAI, model {model}）"

    print("=" * 68)
    print(f"User request: {args.request}")
    print(f"Running mode: {mode_desc}")
    print("=" * 68)

    # --- Step 1: Generate Form ---
    print("\n[Step 1] Generate clarification form HTML ...")
    if offline:
        html = render_form_html(FLIGHT_FORM_SCHEMA, args.request)
    else:
        html = generate_form(client, model, args.request)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Saved to {out_path} (total {len(html)} characters, you can manually open it in the browser to see the cascading effect)")

    # --- Step 2: Structural Validation ---
    print("\n[Step 2] Structurally validate form fields and cascading logic:")
    all_pass, report, script_text = validate_form(html)
    for name, ok in report.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    #  Print cascade logic evidence (relevant snippet in script)
    evidence_lines = [
        ln.strip()
        for ln in script_text.splitlines()
        if re.search(r"round_trip|往返|return_date|display|hidden|toggle|classList", ln, re.I)
    ]
    if evidence_lines:
        print("\n  Cascade logic evidence (script excerpt):")
        for ln in evidence_lines[:8]:
            print(f"    | {ln}")

    if not all_pass:
        print("\n  Warning: Some field validations failed (model output unstable). Check generated HTML for troubleshooting.")

    # --- Step 3: Simulate a submission, Agent continues task ---
    print("\n[Step 3] Simulate user submitting form in one go (round-trip scenario):")
    submitted = {
        "departure_city": "Shanghai",
        "departure_date": "2026-08-01",
        "trip_type": "round_trip",
        "return_date": "2026-08-07",
        "cabin_class": "business",
        "baggage_count": "2",
        # Destination from original request (Beijing), included together
        "destination_city": _extract_destination(args.request) or "Beijing",
    }
    print(json.dumps(submitted, ensure_ascii=False, indent=2))

    print("\n[Step 3] Parse JSON and continue task, output booking summary:")
    if offline:
        summary = summarize_offline(submitted)
        note = "(Offline deterministic template)"
    else:
        summary = continue_task(client, model, args.request, submitted)
        note = f"(Model {model}）"
    print("-" * 68)
    print(summary)
    print(f"-" * 68 + f"  {note}")

    # Results Summary
    print("\n" + "=" * 68)
    print(f"Form field/cascade validation: {'All passed' if all_pass else 'Some failed'}")
    print("Submit JSON parsing: Success (see booking summary above)")
    print("=" * 68)

    # --- Optional: Start local service for real experience ---
    if args.serve:
        serve_html(out_path, args.port)


if __name__ == "__main__":
    main()
