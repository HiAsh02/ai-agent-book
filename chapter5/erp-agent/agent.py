"""
NL -> SQL Agent (artifact mode).

The Agent is only responsible for "generating SQL artifacts", not for moving data itself:
The actual data query is executed by the system (demo.py) using the generated SQL on SQLite, and the result table is presented directly.
"""

import os
import re
from datetime import date

from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")

# --- Generic OpenRouter fallback ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def _map_to_openrouter_model(model: str) -> str:
    """Map the direct model name to the OpenRouter ID (non-mappable IDs uniformly fall back to the current cheap flagship)."""
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


def _make_client_and_model(model: str):
    """Construct the client and parse the model name, including a generic OpenRouter fallback. Returns (client, resolved_model).

    - With OPENAI_API_KEY: direct connection; but if model is gpt-5.x and OPENROUTER_API_KEY is also set,
      prefer OpenRouter (direct gpt-5.6 requires organizational real-name authentication).
    - Without OPENAI_API_KEY but with OPENROUTER_API_KEY: switch to OpenRouter (model name auto-mapped).
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    orkey = os.environ.get("OPENROUTER_API_KEY")
    prefer_or = bool(orkey) and (model or "").lower().startswith("gpt-5")
    if prefer_or or (not api_key and orkey):
        api_key, base_url, model = orkey, OPENROUTER_BASE_URL, _map_to_openrouter_model(model)
    kw = {}
    if api_key:
        kw["api_key"] = api_key
    if base_url:
        kw["base_url"] = base_url
    return OpenAI(**kw), model

SYSTEM_PROMPT = """You are an ERP data assistant for "natural language to SQL".
The user gives you a Chinese question, and you output only one directly executable **SQLite** SQL query, without any explanation or markdown code block.

Today's date is {today}. But **strictly avoid hardcoding year numbers in SQL** (e.g., '2024', '2022-01-01'),
always use strftime(...,'now',...) to derive from the database's current date to avoid year guessing errors.

Database schema (SQLite):
  employees(emp_id INTEGER primary key, name, department, level [higher number means higher level],
            hire_date 'YYYY-MM-DD', leave_date 'YYYY-MM-DD', NULL means active)
  salaries(emp_id, pay_date 'YYYY-MM-01' [one record per month], salary)
  salaries.emp_id references employees.emp_id.

Business and dialect conventions:
  - "this year" = strftime('%Y','now'), "last year" = strftime('%Y','now','-1 year'),
    "the year before last" = strftime('%Y','now','-2 years').
  - For "today" use date('now') (without time part); days between two dates use
    julianday(date('now')) - julianday(hire_date).
  - "Department A" = R&D, "Department B" = Sales.
  - "Active" means leave_date IS NULL.
  - Pay month can be obtained with strftime('%Y-%m', pay_date) as 'YYYY-MM'.
  - Output only one SELECT (may include WITH/CTE), do not write multiple statements or DDL/DML.

Strictly organize the columns and order of SELECT according to the "return columns" requirement attached by the user.
"""


class SQLAgent:
    def __init__(self, model: str = MODEL):
        self.client, self.model = _make_client_and_model(model)

    def generate_sql(self, nl_question: str, hint: str) -> str:
        user = f"Question:{nl_question}\nRequirements:{hint}\nPlease output only one SQLite SQL."
        #Reasoning models (gpt-5 / o series etc.) do not accept temperature=0.
        _reasoning = any(k in (self.model or "").lower()
                         for k in ("gpt-5", "o1", "o3", "o4", "thinking", "reasoner", "kimi-k3"))
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=1 if _reasoning else 0,
            messages=[
                {"role": "system",
                 "content": SYSTEM_PROMPT.format(today=date.today().isoformat())},
                {"role": "user", "content": user},
            ],
        )
        return _clean_sql(resp.choices[0].message.content)


def _clean_sql(text: str) -> str:
    """Remove markdown code block fences and other impurities, keep only SQL."""
    text = text.strip()
    # Remove ```sql ... ``` or ``` ... ```
    fence = re.match(r"^```(?:sql)?\s*(.*?)\s*```$", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    # Remove possible leading backticks
    text = text.strip("`").strip()
    return text
