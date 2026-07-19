# Experiment 5-9: Intent Clarification System with Dynamic Form Generation (★★)

## Objective

Verify that when an Agent faces a user request with **incomplete information**, instead of asking questions one by one, it **dynamically generates a self-contained HTML form** to clarify the intent all at once. The form has built-in **cascading logic** (some fields only appear under certain selections, some dropdown options change dynamically based on another field), and the user can **submit once** to provide all missing information; the frontend aggregates the form into JSON and sends it back to the Agent, which parses it and continues the task.

Acceptance scenario: User inputs "I want to book a flight to Beijing", the Agent generates a form containing:
- Departure city (text input)
- Departure date (date picker)
- Trip type (radio: one-way / round-trip)
- **Return date (only shown when "round-trip" is selected)** ← Cascading logic ①: show/hide
- Cabin class (dropdown: economy / business / first class)
- **Free checked baggage allowance (options change dynamically based on "cabin class")** ← Cascading logic ②: dynamic options

## Mechanism

`demo.py` verifies in three steps. The two running modes have identical mechanisms, differing only in "who writes the form code":

- **Online (default)**: Sends the user request to OpenAI, with a system prompt constraining it to output a self-contained HTML (inline `<style>` + `<script>`, containing cascading display logic and "submit aggregates to JSON" logic). Requires `OPENAI_API_KEY`.
- **Offline (`--offline`)**: Does not call the LLM, uses a built-in flight ticket schema to **deterministically render** the same cascading form, no API Key needed. The offline-rendered form is also fully functional, can be opened in a browser, and contains **two types** of cascading logic (show/hide + dynamic dropdown options). Automatically falls back to offline mode when `OPENAI_API_KEY` is not set.

Three-step flow:

1. **Generate Form**: Online via model generation, or offline via built-in schema rendering, saved as `generated_form.html` (path can be overridden with `--output`).
2. **Structural Validation (no browser needed)**: Uses BeautifulSoup + regex to check that the form indeed contains the required fields, and that the return date field has a JS toggle logic for "only show on round-trip", printing script evidence of cascading logic.
3. **Simulated Submission**: Constructs a user-submitted JSON (round-trip scenario), feeds it back to the Agent; the Agent parses it and outputs a booking summary (online via model, offline via deterministic template), verifying the "parse JSON → continue task" loop.

## Running

```bash
pip install -r requirements.txt
cp env.example .env                 # Fill in OPENAI_API_KEY (if not configured, set OPENROUTER_API_KEY to automatically switch to OpenRouter)

python demo.py                      # Online: Agent calls OpenAI to generate (requires API Key)
python demo.py --offline            # Offline: Built-in schema deterministic rendering, no API Key needed
python demo.py --offline --serve    # Offline render then start local server, browser real-time experience of cascading/submission
python demo.py --model gpt-5.6     # Optional: Override online model (ignored under --offline)
python demo.py --request "I want to book a flight to Tokyo"   # Optional: Custom vague request
python demo.py --help               # View all parameters
```

Command-line arguments:

| Parameter | Description | Default |
| --- | --- | --- |
| `-r` / `--request TEXT` | User's vague request (intent) | `I want to book a flight to Beijing` |
| `-o` / `--output PATH` | Output path for generated HTML (relative paths resolved relative to script directory) | `generated_form.html` |
| `--model NAME` | Override online model name (ignored under `--offline`) | Environment variable `MODEL`, default `gpt-5.6-luna` |
| `--offline` | Offline mode: built-in schema deterministic rendering, no API Key needed | Off (auto-enabled when Key not set) |
| `--serve` | Start local HTTP server after generation and open browser, real experience of cascading/submission | Off |
| `--port N` | Port used by `--serve` | `8000` |

After running:
- The generated form is saved as `generated_form.html`, can be **manually opened in a browser** (or auto-opened with `--serve`). Toggle "one-way/round-trip" to see the cascading display effect of the return date field, switch cabin class to see the dynamic update of baggage allowance dropdown, click "submit" to print the aggregated JSON at the bottom of the page.
- The terminal prints field validation results, cascading logic evidence, and the Agent's parsing summary of the submitted JSON.

Environment variables:
- `OPENAI_API_KEY` (required for online mode; automatically falls back to offline mode when not set)
- `OPENAI_BASE_URL` (optional, compatible with OpenAI protocol third-party endpoints)
- `MODEL` (optional, default `gpt-5.6-luna`)

## Real Run Output

**Offline mode (`--offline`, deterministic rendering, no API Key needed)**

```
[Step 2] Structural validation of form fields and cascading logic:
  [PASS] Departure city (text input)
  [PASS] Departure date (date picker)
  [PASS] Trip type (radio: one-way)
  [PASS] Trip type (radio: round-trip)
  [PASS] Return date (date picker)
  [PASS] Return field cascading logic (only show on round-trip)

[Step 3] Parse JSON and continue task, output booking summary:
Received your booking information: Shanghai → Beijing, departure date 2026-08-01.
Trip type: round-trip, return date 2026-08-07.
Cabin class: business, free checked baggage 2 pieces.
Searching for flights...
```

**Online mode (default, model `gpt-5.6-luna`)**

```
[Step 2] Structural validation of form fields and cascading logic:
  [PASS] Departure city (text input) / [PASS] Departure date (date picker)
  [PASS] Trip type (radio: one-way/round-trip) / [PASS] Return date (date picker)
  [PASS] Return field cascading logic (only show on round-trip)

  Cascading logic evidence (script excerpt):
    | const returnDateField = document.getElementById('return_date_field');
    | returnDateField.style.display = roundTrip ? 'block' : 'none';

[Step 3] Agent parses JSON and continues task, outputs booking summary:
Your selected itinerary is: departing from Shanghai, arriving in Beijing. Departure date is August 1, 2026, return date is August 7, 2026. Trip type is round-trip, cabin class is business, checked baggage count is 2 pieces. Searching for flights...
```

## Limitations

- **Field naming not fully controllable (online mode only)**: Different models/temperatures may produce different `name` and id conventions. The system prompt has agreed on English `name` identifiers (`departure_city` / `departure_date` / `trip_type` / `return_date`), and validation uses **robust keyword/attribute matching** (first looks for agreed names, falls back to semantic matching + text keywords), so occasional naming drift usually still passes. If an item `FAIL`s, open `generated_form.html` to see the model's actual output. Offline mode uses built-in schema deterministic rendering, naming/structure is completely stable, not subject to this limitation.
- **Two types of cascading effect validation**: By default, no real browser is needed; cascading logic is indirectly verified through "static JS parsing + keyword matching". To see real cascading click effects, add `--serve` (offline-rendered form + local server) or manually open the generated HTML.
- **Submission is simulated**: Step 3 uses a constructed JSON instead of real frontend submission, to verify the Agent's "parse → continue task" loop; in a real system, this JSON would be POSTed back to the backend by the form's `submit` callback.
- Online generation quality depends on the model; `temperature=0` is used for maximum reproducibility.
