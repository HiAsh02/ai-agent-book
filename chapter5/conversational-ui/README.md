# Experiment 5-11: Conversational Interface Customization System (★★)

Users propose UI customization requirements (colors / fonts / text / layout / component positions) using **natural language**,
the Agent autonomously **locates and modifies the frontend source code**, and the **Hot Module Replacement (HMR)** in development mode makes changes take effect instantly,
supporting multi-round iterative customization.

## Purpose

Transform a "one-size-fits-all" standard frontend into a "thousand faces for thousand users" conversational customizable interface:

- Basic chatbot application = **React(Vite) frontend + FastAPI backend**;
- Both frontend and backend run in development mode: frontend Vite **HMR**, backend uvicorn **--reload**;
- User says "change the send button to blue / switch to monospace font / change the title to XXX",
  Agent (OpenAI, default `gpt-5.6-luna`; if `OPENAI_API_KEY` is not configured, set `OPENROUTER_API_KEY` to automatically switch to OpenRouter) understands the requirement → modifies source files in `frontend/src`;
- Hot reload detects file changes, the browser sees interface changes without a full page refresh.

## Principle / Architecture (Brief)

The entire system consists of four parts, each with its own role:

- **`agent.py` (Customization Agent)**: The core. Feeds one natural language requirement + the current editable source code to OpenAI,
  uses the `apply_edits` tool via function calling to let the model return the "rewritten full file content".
  Only exposes whitelisted files (`src/App.jsx`, `src/theme.css`) to the model, and validates the path after return,
  preventing the model from modifying/adding incorrect files. It only produces the rewriting plan, **does not write to disk** (facilitates diff display and validation).
- **`baseline/src/` (Baseline Snapshot)**: The "factory original" of the frontend source code. `demo.py` copies it back to `frontend/src` before each round,
  ensuring repeatable results across multiple runs without cross-contamination—this also serves as the comparison baseline for the Agent's changes versus the original interface.
- **`frontend/` (React + Vite Frontend)**: The object being customized. The Agent modifies `src/*` here;
  Vite **HMR** in development mode makes changes instantly visible, `vite build` is used to verify "changes didn't break the application".
- **`backend/` (FastAPI Backend)**: Minimal chatbot service (`/api/chat`), providing a conversational carrier for the frontend;
  default **echo** mode (works out of the box, no API Key required), or use `--model` to switch to **real LLM conversation** with one command;
  comes with a command-line entry point (`python main.py --help`), `--reload` demonstrates "backend hot reload". It does not participate in UI customization,
  it is a supporting role to make the entire interface actually run.

In one sentence: **Agent reads requirement → modifies frontend source code → asserts changes take effect + build is not broken**,
`baseline` ensures repeatability, `backend` enables the interface to actually converse.

## About Hot Module Replacement (HMR)

- **Frontend**: The Vite dev server started with `npm run dev` has built-in HMR. As soon as the Agent modifies `src/*.jsx`
  or `src/theme.css`, the browser performs a local hot replacement, preserving application state, and the interface updates instantly.
- **Backend**: `uvicorn main:app --reload` monitors `.py` changes and restarts automatically.
- The customization in this experiment mainly targets the frontend source code, so the visual effect is reflected through frontend HMR.

## Directory Structure

```
conversational-ui/
├── frontend/                 # React + Vite frontend (basic chatbot interface)
│   ├── src/App.jsx           #   Interface and UI text (Agent modifies "text/components")
│   ├── src/theme.css         #   Color/font/layout styles (Agent modifies "styles")
│   ├── src/main.jsx
│   ├── index.html
│   ├── vite.config.js        #   Enables HMR + /api proxy to backend
│   └── package.json
├── backend/
│   ├── main.py               # FastAPI backend (/api/chat)
│   └── requirements.txt
├── baseline/src/             # Initial snapshot of frontend source code (restored before each demo run, ensuring repeatability)
├── agent.py                  # Customization Agent: NL requirement → rewrites source code using OpenAI
├── demo.py                   # End-to-end demo + automatic validation (NL→code→assertion→build)
├── requirements.txt          # Backend + Agent dependencies
├── env.example
└── .gitignore                # node_modules / dist / .env are all ignored
```

## How to Run

### 1) Prepare Environment

```bash
# Python dependencies (Agent + Backend)
pip install -r requirements.txt

# Frontend dependencies (first npm install may be slow, which is normal)
cd frontend && npm install && cd ..

# Configure OpenAI Key
cp env.example .env   # Then fill in OPENAI_API_KEY (or set OPENROUTER_API_KEY as fallback)
```

### 2) Automated Validation Loop (No Browser Required)

```bash
python demo.py            # Run all 3 customization rounds with full validation
python demo.py --quick    # Run only round 1 (saves time, for quick smoke test)
python demo.py --rounds 2 # Run only the first 2 rounds
python demo.py --no-build # Skip vite build (only verify "changes are correctly applied", faster)
python demo.py -h         # View all parameters
```

`demo.py` will run 3 consecutive rounds of natural language customization. Each round:
Calls real OpenAI to rewrite source code → prints the diff of changes → reads back the source code and asserts "changes meet requirements" →
`vite build` verifies "application is not broken". The first round is often slower due to `npm install` or the initial build;
for a quick test, use `--quick` or `--no-build`.

### 3) Manual Experience of Real HMR (Optional, Requires Browser)

```bash
# Terminal A: Backend (hot reload). Both startup methods behave identically, choose either:
cd backend && python main.py --reload --port 8000          # This file has its own command-line entry point
#   Or: cd backend && uvicorn main:app --reload --port 8000   # Example from the book
#   To make the running chatbot actually talk (instead of echo): add --model gpt-5.6-luna (requires OPENAI_API_KEY or OPENROUTER_API_KEY)

# Terminal B: Frontend (HMR)
cd frontend && npm run dev
# Open http://localhost:5173

# Terminal C: Run a customization requirement, then go back to the browser to see the interface change instantly
python -c "import agent,pathlib; c,m=agent.build_client_and_model(); \
r=agent.customize(c,m,pathlib.Path('frontend'),'change the send button to orange'); \
[pathlib.Path('frontend',f['path']).write_text(f['content']) for f in r['files']]"
```

Backend command-line parameters (`cd backend && python main.py --help`):

| Parameter | Description | Default |
| --- | --- | --- |
| `--host` | Listen address (use `0.0.0.0` for external access) | `127.0.0.1` |
| `--port` | Listen port (frontend proxies `/api` to this port) | `8000` |
| `--reload` / `--no-reload` | Whether to enable backend hot reload | Enabled |
| `--model NAME` | Specify model name, switch to real LLM conversation; default is echo mode (can also use environment variable `CHAT_MODEL`) | None (echo) |
| `--log-level` | uvicorn log/output level | `info` |
| `--print-config` | Only print effective configuration (JSON) and exit, do not listen on port (useful for validation in portless environments) | Off |

> Both echo and LLM modes do not affect the UI customization loop—customization acts on the **frontend source code**, the backend is merely a carrier for the interface to actually converse.
> The LLM mode reuses the same `OPENAI_API_KEY` / `OPENAI_BASE_URL` configuration as `agent.py`; if the key is missing or the call fails, it will automatically fall back to a placeholder prompt, never fabricating a response.

## Validation Methods and Limitations

- **What this demo automatically validates**: The loop from natural language → code modification is **correctly applied** and **does not break the build**.
  - Reads back the source code and asserts: e.g., "change to blue #2563eb" → the color value indeed appears in the source code;
    "switch to monospace font" → `monospace` appears; "change title to XXX" → the text appears.
  - After each round of changes, `vite build` must compile successfully, proving the changes did not break the application.
- **What this demo does NOT do**: The **visual** instant refresh of HMR in a real browser.
  There is no Playwright/browser on this machine, so it cannot automatically take screenshots to verify the visual effect—
  this part requires manually running `npm run dev` + opening a browser to view (see step 3 above).
- The Agent is only allowed to modify whitelisted files (`src/App.jsx`, `src/theme.css`),
  reducing the risk of modifying the wrong files; the modification uses "full file rewrite", which is more stable for small files than piecemeal replacements.

## Real Run Output (Excerpt)

```
Round 1 NL customization requirement: Change the theme color of the send button and user message bubbles from green to blue, using #2563eb.
[Modified file] src/theme.css
  - --color-primary: #16a34a;   /* Initially green */
  + --color-primary: #2563eb;   /* Changed to blue */
Assertion: Blue value #2563eb appears in source code -> Passed ✅
Build result: Passed ✅

Round 2 NL customization requirement: Change the entire interface font to monospace.
[Modified file] src/theme.css
  - --font-family: system-ui, "PingFang SC", ... sans-serif;
  + --font-family: monospace;
Assertion: Monospace font appears in source code -> Passed ✅
Build result: Passed ✅

Round 3 NL customization requirement: Change the top title text to "My Personal Assistant".
[Modified file] src/App.jsx
  - const HEADER_TITLE = "Smart Assistant";
  + const HEADER_TITLE = "My Personal Assistant";
Assertion: New title text "My Personal Assistant" appears in source code -> Passed ✅
Build result: Passed ✅

Multi-round customization summary: All passed ✅
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `OPENAI_API_KEY` | One of these is required; this experiment reads this item (uses `OPENROUTER_API_KEY` as fallback if not configured) |
| `OPENAI_BASE_URL` | Optional, switch to a service endpoint compatible with the OpenAI protocol |
| `MODEL` | Optional, default `gpt-5.6-luna` |

## How to Adapt / Extend

- **Change model / change provider**: The Agent uses the standard OpenAI SDK; any service "compatible with the OpenAI protocol" can be connected.
  Simply set `OPENAI_BASE_URL` + `MODEL` + the corresponding `OPENAI_API_KEY` in `.env` or environment variables,
  no code changes needed. For example:
  - Kimi / Moonshot: `OPENAI_BASE_URL=https://api.moonshot.cn/v1`, `MODEL=kimi-k3`;
  - Volcano Ark (ARK): `OPENAI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`, `MODEL=<endpoint-id>`;
  - Local vLLM / Ollama, etc.: Point `OPENAI_BASE_URL` to the local endpoint.
- **Expand the customization scope**: By default, only `src/App.jsx` and `src/theme.css` are allowed to be modified. To allow the Agent to modify more files,
  add or remove paths in the `EDITABLE_FILES` whitelist in `agent.py` (the larger the whitelist, the more flexible, but also the greater the risk of modifying the wrong file).
- **Add new validation rounds**: Append `{"requirement": ..., "verify": ...}` to the `ROUNDS` list in `demo.py`,
  to incorporate your own customization requirements into the automated assertion loop.- **Frontend integration**: `frontend/` is a standard Vite project. Run `npm run dev` for HMR, or `npm run build` to generate static assets.  
  To use your own UI, replace `src/*` and update the whitelist and `baseline/` snapshots accordingly.  
- **Backend integration / real LLM chat**: The `/api/chat` endpoint in `backend/main.py` defaults to an echo-style placeholder response.  
  Add `--model <model_name>` (or set `CHAT_MODEL`) to switch to real LLM chat (reusing the `OPENAI_*` configuration above) and turn it into a real agent.  
  To replace it with custom business logic, modify the return in `_llm_reply` or `chat`.
