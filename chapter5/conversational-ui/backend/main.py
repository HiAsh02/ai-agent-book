"""Experiment 5-11: Conversational Interface Customization System — FastAPI Backend.

A minimal chatbot backend: the frontend POSTs user messages to /api/chat, and the backend returns replies.
In development mode, start with `uvicorn main:app --reload`; changes to backend code will automatically reload
(corresponding to the "FastAPI hot reload" mentioned in the book).

Two reply modes (default is "echo" placeholder, focusing on the UI customization theme):
  - **echo (default)**: The backend echoes the user message as-is, no model key required, ready to use out of the box;
  - **llm (optional)**: After setting a model, uses real LLM conversation, making the running chatbot actually talk.
    Enable via command line `--model` or environment variable `CHAT_MODEL`, reusing the same
    OPENAI_API_KEY / OPENAI_BASE_URL configuration as agent.py.

Startup methods (choose one, behavior identical):
  uvicorn main:app --reload --port 8000      # Book example: module-level app + uvicorn hot reload
  python main.py --reload --port 8000        # Command-line entry included in this file (see --help)
"""

import os
import argparse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:  # dotenv optional: allows --model mode to also read OPENAI_API_KEY from .env
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

app = FastAPI(title="Conversational UI Backend")

# Allow the frontend (Vite dev server, 5173) to make cross-origin requests directly, convenient for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


def _chat_model() -> str:
    """Current reply mode: if a model name is returned, use real LLM; if empty string, default echo mode.

    Read from environment variable CHAT_MODEL (not module-level constant), so that even if `--reload` triggers
    a child process that re-imports this module, it can still get the model setting passed via command line through the environment variable.
    """
    return (os.getenv("CHAT_MODEL") or "").strip()


def _llm_reply(message: str, model: str) -> str:
    """Generate reply using real LLM, reusing the same OPENAI_* configuration as agent.py.

    Any exception degrades to a clear prompt (never fabricates replies), ensuring the frontend doesn't go blank.
    """
    try:
        from openai import OpenAI
    except Exception:
        return "(openai dependency not installed, cannot enable LLM mode; falling back to placeholder reply)"

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    orkey = os.getenv("OPENROUTER_API_KEY")
    # Generic OpenRouter fallback: when no direct key, or for gpt-5.x (direct connection requires organization real-name authentication), switch to OpenRouter.
    prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        api_key, base_url = orkey, "https://openrouter.ai/api/v1"
        if "/" not in model:
            model = ("openai/" + model) if model.lower().startswith(("gpt-", "o1", "o3", "o4")) else "openai/gpt-5.6-luna"
    if not api_key:
        return "(OPENAI_API_KEY or OPENROUTER_API_KEY not configured, cannot enable LLM mode; falling back to placeholder reply)"

    client_kwargs = {"api_key": api_key, "timeout": 60.0, "max_retries": 2}
    if base_url:
        client_kwargs["base_url"] = base_url

    try:
        client = OpenAI(**client_kwargs)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful Chinese intelligent assistant, answering concisely and friendly."},
                {"role": "user", "content": message},
            ],
            temperature=(1 if any(k in (model or "").lower()
                                  for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
                         else 0.7),
        )
        return resp.choices[0].message.content or "(Model returned empty reply)"
    except Exception as e:  # Catches network/auth/model name issues here
        return f"(Failed to call LLM: {e}; falling back to placeholder reply)"


@app.get("/api/health")
def health():
    model = _chat_model()
    return {"status": "ok", "mode": "llm" if model else "echo", "model": model or None}


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Default echo reply; set CHAT_MODEL to use real LLM conversation.

    This experiment focuses on "conversational UI customization", the backend logic is intentionally minimal;
    for a real customer service experience, use `python main.py --model <model_name>` to enable LLM mode.
    """
    model = _chat_model()
    if model:
        return {"reply": _llm_reply(req.message, model)}
    return {"reply": f"I received your message: {req.message}"}


# ---------------------------------------------------------------------------
# Command-line entry: allows the backend to start with either `uvicorn main:app --reload` or `python main.py`
# and control host/port/hot reload/reply mode/logging via arguments.
# ---------------------------------------------------------------------------
def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Experiment 5-11: Conversational Interface Customization System — FastAPI Backend (minimal chatbot service)."
        "Provides /api/chat endpoint for the customizable conversational frontend, with --reload to demonstrate backend hot reload in development mode.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Listen address; use 0.0.0.0 for external access.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Listen port (frontend vite.config.js proxies /api to 8000 by default).",
    )
    reload_group = parser.add_mutually_exclusive_group()
    reload_group.add_argument(
        "--reload",
        dest="reload",
        action="store_true",
        default=True,
        help="Enable hot reload: changes to backend .py files automatically restart (enabled by default in development).",
    )
    reload_group.add_argument(
        "--no-reload",
        dest="reload",
        action="store_false",
        help="Disable hot reload (closer to production operation).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("CHAT_MODEL") or None,
        metavar="NAME",
        help="Enable real LLM conversation and specify model name (e.g., gpt-5.6-luna);"
        "default is echo mode if omitted. Can also be set via environment variable CHAT_MODEL.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="uvicorn log/output level.",
    )
    parser.add_argument(
        "--print-config",
        action="store_true",
        help="Only print effective configuration (JSON) and exit, without actually listening on a port (useful for verification in environments without network/ports).",
    )
    return parser.parse_args(argv)


def main(argv=None):
    import json

    args = parse_args(argv)

    # Write --model back to environment variable: so that child processes spawned by --reload, which re-import this module,
    # can also detect LLM mode via CHAT_MODEL (child processes do not share this function's local state).
    if args.model:
        os.environ["CHAT_MODEL"] = args.model
    else:
        os.environ.pop("CHAT_MODEL", None)

    config = {
        "host": args.host,
        "port": args.port,
        "reload": args.reload,
        "mode": "llm" if args.model else "echo",
        "model": args.model,
        "log_level": args.log_level,
    }

    if args.print_config:
        print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0

    import uvicorn

    print(
        f"Start FastAPI backend: http://{args.host}:{args.port}"
        f"  mode={config['mode']}"
        f"  hot reload={'On' if args.reload else 'Off'}"
    )
    # Use import string to work under --reload; run `python main.py` from the backend/ directory.
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
