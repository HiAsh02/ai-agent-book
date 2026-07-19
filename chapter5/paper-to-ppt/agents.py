"""
Two agents, Proposer and Reviewer, along with an LLM client with token metering.

Design highlights (corresponding to the "Proposer-Reviewer" mechanism in the book):
  - Proposer only handles **text**: paper body + accumulated structured text feedback; never receives rendered images.
  - Reviewer **only sees the latest rendered screenshot** each round, and each round is a fresh, history-free call.
  - In contrast, the single-agent self-review baseline accumulates all previous rendered images in the same conversation, causing rapid context expansion.

All calls to OpenAI go through TokenMeter to count prompt/completion tokens,
for the final "single-agent vs dual-agent context consumption" comparison.
"""
import base64
import io
import json
import os
import re

from openai import OpenAI
from PIL import Image

#  Model used for text generation (Proposer / text part of single agent)  
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gpt-5.6-luna")
#  The model used for visual review (Reviewer / single Agent's image-reading part) must support images
VISION_MODEL = os.environ.get("VISION_MODEL", "gpt-5.6-luna")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def map_model_to_openrouter(model: str) -> str:
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

# Scale the screenshot to this width before sending to Vision, balancing "clear text overflow" and "controlling token cost".
VISION_IMAGE_WIDTH = 1280


class TokenMeter:
    """Accumulate tokens consumed by a "role/mode" and record the prompt tokens for each call (to observe context peaks)."""

    def __init__(self, name: str):
        self.name = name
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.peak_prompt_tokens = 0  # Maximum prompt tokens per call — determines whether the context is "blown up"
        self.per_call_prompt = []

    def add(self, usage):
        self.calls += 1
        pt = usage.prompt_tokens
        self.prompt_tokens += pt
        self.completion_tokens += usage.completion_tokens
        self.peak_prompt_tokens = max(self.peak_prompt_tokens, pt)
        self.per_call_prompt.append(pt)

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens


def _client() -> OpenAI:
    # General OpenRouter fallback: when there is no direct key, or the default gpt-5.x (direct connection requires organizational real-name authentication) is used, switch to OpenRouter.
    global TEXT_MODEL, VISION_MODEL
    api_key = os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    orkey = os.environ.get("OPENROUTER_API_KEY")
    prefer_or = bool(orkey) and (
        (TEXT_MODEL or "").lower().startswith("gpt-5") or (VISION_MODEL or "").lower().startswith("gpt-5")
    )
    if prefer_or or (not api_key and orkey):
        api_key, base_url = orkey, OPENROUTER_BASE_URL
        # When going through OpenRouter, map the model name to its id (idempotent: ids already with prefix are returned as-is).
        TEXT_MODEL = map_model_to_openrouter(TEXT_MODEL)
        VISION_MODEL = map_model_to_openrouter(VISION_MODEL)
    if not api_key:
        raise SystemExit(
            "❌ OPENAI_API_KEY (or fallback OPENROUTER_API_KEY) not detected. Please `cp env.example .env` first and fill in a valid "
            "Run after setting the OpenAI API Key (or `export OPENAI_API_KEY=sk-...` / `export OPENROUTER_API_KEY=...`)."
        )
    # timeout + max_retries: Single network jitter/SSL interruptions will be automatically retried, rather than crashing the entire pipeline.
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=60.0,
        max_retries=4,
    )


def encode_image(path: str) -> str:
    """Read the PNG, scale to a uniform width, and encode as a data URL (base64)."""
    img = Image.open(path).convert("RGB")
    if img.width > VISION_IMAGE_WIDTH:
        h = int(img.height * VISION_IMAGE_WIDTH / img.width)
        img = img.resize((VISION_IMAGE_WIDTH, h), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"


def _extract_json(text: str):
    """Robustly extract JSON from model responses (tolerating ```json code blocks or surrounding extra text)."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    #  find the first { to the last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def _extract_slides_md(text: str) -> str:
    """Extract slides.md content from model response (tolerate ```markdown wrapping)."""
    m = re.search(r"```(?:markdown|md)?\s*(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


# --------------------------------------------------------------------------- #
# Reviewer's review scoring criteria (Proposer / Single Agent / Independent reviewer share the same rubric)
# --------------------------------------------------------------------------- #
REVIEW_RUBRIC = """You are a strict presentation quality reviewer (Reviewer). You will see a PPT rendered by Slidev,
each image corresponds to one slide (numbered sequentially, starting from page 1). Please check each page for the following issues:

- text_overflow (text overflowing/cropped beyond page boundaries)
- overcrowded (too much content/too crowded/insufficient whitespace)
- image_size (image too large breaking layout, or too small to see clearly)
- readability (font too small, poor contrast, code blocks hard to read)
- layout (alignment chaos, unbalanced title-to-body ratio, empty pages)

Please review with a strict standard where the **target audience is the listeners** — if a slide has more than about 5 bullet points, or the body text block is too long, or an image squeezes text space, it should be considered an overcrowded/image_size issue. Report real problems, but do not overlook "overstuffed" slides. For each issue, provide: page (page number, integer),
issue_type (one of the above), severity (high/medium/low), suggestion (specific, actionable modification suggestion, in Chinese).

Also provide:
- overall_score: overall quality score from 0-100 (higher is better)
- pass: boolean, true only if the entire PPT **has no high or medium severity issues** and the layout is clean and readable

Output strictly the following JSON (do not output any extra text):
{
  "overall_score": <int>,
  "pass": <bool>,
  "issues": [
    {"page": <int>, "issue_type": "<type>", "severity": "<high|medium|low>", "suggestion": "<Chinese suggestion>"}
  ]
}"""


class Reviewer:
    """Reviewer Agent: Look at the latest rendering screenshot and output structured JSON suggestions. Each round is called independently, no history."""

    def __init__(self, meter: TokenMeter):
        self.client = _client()
        self.meter = meter

    def review(self, png_paths: list[str]) -> dict:
        content = [{"type": "text",
                    "text": f"This PPT has a total of {len(png_paths)} page, the rendering screenshots of each page are given below in page number order. Please review."}]
        for i, p in enumerate(png_paths, 1):
            content.append({"type": "text", "text": f"Page {i} :"})
            content.append({"type": "image_url",
                            "image_url": {"url": encode_image(p), "detail": "high"}})
        resp = self.client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {"role": "system", "content": REVIEW_RUBRIC},
                {"role": "user", "content": content},
            ],
            temperature=0.2,
        )
        self.meter.add(resp.usage)
        return _extract_json(resp.choices[0].message.content)


PROPOSER_SYSTEM = """You are a Proposer Agent skilled at converting academic papers into presentations.
You write the PPT source code slides.md using the Slidev framework (Markdown + HTML).

Slidev syntax essentials:
- The file starts with YAML frontmatter (enclosed by ---), setting theme: default.
- Use a single line `---` (with blank lines before and after) to separate each slide.
- The first slide usually contains the title, authors, and conference.
- Reference images using markdown: ![description](/image_filename.png), or use HTML to control size,
  e.g., <img src="/speedup_bar.png" class="h-60 mx-auto" />.
- Use Windi/Uno CSS utility classes to control layout (e.g., text-sm, grid grid-cols-2 gap-4).

Requirements:
- Generate about 8-12 slides covering the paper's title, background/motivation, method, experimental results, and conclusion.
- Use the provided charts/tables on at least 3 slides, ensuring the text matches the visuals.
- Keep each slide moderately informative; avoid cramming too much text; split into more slides rather than overflowing.
- Output only the complete content of slides.md, wrapped in a ```markdown code block, with no extra explanation."""


class Proposer:
    """Proposer Agent: Only consumes text (papers + cumulative text feedback), outputs slides.md."""

    def __init__(self, meter: TokenMeter, paper_md: str, figures: dict):
        self.client = _client()
        self.meter = meter
        fig_desc = "\n".join(f"- {name}：{desc}" for name, desc in figures.items())
        first_user = (
            f"Below is the full text of the paper (Markdown):\n\n{paper_md}\n\n"
            f"Directly referenceable chart file (placed in Slidev public directory, referenced with /filename): \n{fig_desc}\n\n"
            f"Please first produce a **quick draft**: to expedite the draft, compress the entire paper to **within 4 pages** —"
            f"Directly paste the **complete original paragraph** corresponding to each chapter onto the slide (keep the entire text, do not condense into bullet points for now)."
            f"Also include both charts. (A reviewer will later check the actual rendering and help you adjust it.) Generate the complete slides.md."
        )
        # Proposer's conversation history — only text accumulates, images are never added
        self.messages = [
            {"role": "system", "content": PROPOSER_SYSTEM},
            {"role": "user", "content": first_user},
        ]

    def _generate(self) -> str:
        resp = self.client.chat.completions.create(
            model=TEXT_MODEL, messages=self.messages, temperature=0.3,
        )
        self.meter.add(resp.usage)
        reply = resp.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return _extract_slides_md(reply)

    def propose(self) -> str:
        """First round generation."""
        return self._generate()

    def revise(self, review: dict) -> str:
        """Revise based on Reviewer's structured text feedback (only add JSON text to context)."""
        feedback = json.dumps(review, ensure_ascii=False, indent=2)
        self.messages.append({
            "role": "user",
            "content": (
                "Reviewer rendered screenshots of each page of your previous slides.md,"
                "and provides the following structured improvement suggestions (JSON):\n\n"
                f"{feedback}\n\n"
                "Please understand these issues and revise slides.md (you can split pages, simplify text, adjust image sizes, etc.),"
                "and output the complete revised slides.md."
            ),
        })
        return self._generate()


# --------------------------------------------------------------------------- #
# Single Agent self-review control group: in the same conversation, generate, view own rendered images, and revise.
# Key difference: rendered images from previous iterations **remain** in the same context, causing the context to expand rapidly with each iteration.
# --------------------------------------------------------------------------- #
SELF_REVIEW_SYSTEM = PROPOSER_SYSTEM + """

Additionally, you must **self-review**: when receiving screenshots of your own PPT, first mentally identify issues according to the following criteria
(text overflow, content crowding, image size, readability, layout), then output the revised complete slides.md based on that."""


class SelfReviewAgent:
    """Single Agent self-review: a continuously growing conversation, images accumulate in the context."""

    def __init__(self, meter: TokenMeter, paper_md: str, figures: dict):
        self.client = _client()
        self.meter = meter
        fig_desc = "\n".join(f"- {name}：{desc}" for name, desc in figures.items())
        first_user = (
            f"Below is the full text of the paper (Markdown):\n\n{paper_md}\n\n"
            f"Directly referenceable chart files:\n{fig_desc}\n\n"
            f"Please first produce a **quick draft**: to expedite the draft, compress the entire paper to **within 4 pages** —"
            f"Directly paste the **complete original paragraph** corresponding to each chapter onto the slide (keep the entire text, do not condense into bullet points for now)."
            f"Also include the two charts. (You will later see actual rendered screenshots and adjust accordingly.) Generate a complete slides.md."
        )
        self.messages = [
            {"role": "system", "content": SELF_REVIEW_SYSTEM},
            {"role": "user", "content": first_user},
        ]

    def propose(self) -> str:
        resp = self.client.chat.completions.create(
            model=VISION_MODEL, messages=self.messages, temperature=0.3,
        )
        self.meter.add(resp.usage)
        reply = resp.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return _extract_slides_md(reply)

    def self_review_and_revise(self, png_paths: list[str]) -> str:
        """Add the latest rendered screenshot to the **same** context, let the model self-review and revise. Images will remain in history."""
        content = [{"type": "text",
                    "text": (f"This is a screenshot of your previous slides.md rendered into {len(png_paths)} pages."
                             "Please self-review (text overflow/crowding/image size/readability/layout),"
                             "then output the revised complete slides.md.")}]
        for i, p in enumerate(png_paths, 1):
            content.append({"type": "text", "text": f"Page {i} :"})
            content.append({"type": "image_url",
                            "image_url": {"url": encode_image(p), "detail": "high"}})
        self.messages.append({"role": "user", "content": content})
        resp = self.client.chat.completions.create(
            model=VISION_MODEL, messages=self.messages, temperature=0.3,
        )
        self.meter.add(resp.usage)
        reply = resp.choices[0].message.content
        self.messages.append({"role": "assistant", "content": reply})
        return _extract_slides_md(reply)


def independent_judge(png_paths: list[str], meter: TokenMeter) -> dict:
    """Use the same rubric to independently score a final PPT for fair comparison of the quality of the two approaches."""
    reviewer = Reviewer(meter)
    return reviewer.review(png_paths)
