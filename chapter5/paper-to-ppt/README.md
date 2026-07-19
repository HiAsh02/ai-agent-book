# Experiment 5-4: Automatic PPT Generation from Papers (Proposer-Reviewer Mechanism)

Companion to Chapter 5 of "Understanding AI Agents". Reframes "making a PPT" as a **code generation** problem: using the [Slidev](https://sli.dev) framework (Markdown + HTML defines slides), the Agent automatically generates a presentation from a paper, and uses a **Proposer-Reviewer** mechanism for visual quality control.

## One-Sentence Conclusion

The Proposer only writes Slidev code; the Reviewer actually **renders each page as a PNG** and then uses a **Vision LLM to look at the images** to identify issues (text overflow / overcrowded content / image size). The Proposer iteratively revises based on structured feedback. Compared to a "single Agent self-review" (which piles all previous rendered images into the same context), the dual-agent division of labor has a **significantly lower peak context** — because the Proposer never sees images, and the Reviewer only sees the latest version of screenshots each round.

## Why "Render and Then Look"

When the Agent finishes writing Slidev code, it **does not know the actual rendering effect**: whether the content is too cramped, whether text overflows, whether image sizes are appropriate — these can only be seen after rendering into pixels. Therefore, the Reviewer accesses **new information** (the rendering result) that the Proposer cannot see, which is the value of this mechanism.

## Proposer-Reviewer Division of Labor

| Role | Responsibility | What's in the Context |
|---|---|---|
| **Proposer** (`gpt-5.6-luna`, text-only) | Read paper → Plan pages → Generate/revise `slides.md` | Paper text + **accumulated structured text feedback** (never contains images) |
| **Reviewer** (`gpt-5.6-luna`, Vision) | Look at the latest version of each page PNG, output structured suggestions JSON | **Fresh call each round**, only contains the latest version screenshots |

The Reviewer's suggestions are structured and actionable, not vague "looks bad", containing fields:
`page` (page number), `issue_type` (`text_overflow`/`overcrowded`/`image_size`/`readability`/`layout`),
`severity` (high/medium/low), `suggestion` (specific revision suggestion), and overall `overall_score` and `pass`.

Proposer receives feedback → understands intent → revises code → submits to Reviewer again, looping until `pass` or max rounds reached.

## Controlled Experiment: Single Agent Self-Review vs Dual-Agent Division of Labor

`demo.py` runs both schemes simultaneously and uses the **same independent Vision judge** to score the final PPTs from both (ensuring quality comparability):

- **Scheme A Dual Agent**: As above. Proposer context only grows with text; Reviewer resets each round, only sees latest screenshots.
- **Scheme B Single Agent Self-Review**: One Agent generates in the **same conversation** → looks at its own rendered screenshots for self-review → revises. Previous rendered images **stay in the context forever**, rapidly expanding with iterations (the "context quickly exceeds limits" described in the book).

The script prints the prompt token sequence for each call, total amount, and **peak context** (single prompt token, determines whether the context window is exceeded). The more pages and iterations, the more exaggerated Scheme B's peak is compared to Scheme A.

## Running

```bash
# 1) Python dependencies
pip install -r requirements.txt

# 2) Slidev + rendering dependencies (Node). First time takes about 1-2 minutes:
npm install
#   - @slidev/cli: Slidev command line
#   - playwright-chromium: underlying browser for slidev export --format png
#   - typescript: required for Slidev's twoslash code highlighting (otherwise export will ERR_MODULE_NOT_FOUND)
#   If npm install does not automatically install the chromium browser binary, run:
#     npx playwright install chromium

# 3) Configure Key
cp env.example .env    # Fill in OPENAI_API_KEY (if not configured, set OPENROUTER_API_KEY to automatically switch to OpenRouter)

# 4) Run the full pipeline (generate → render → Vision review → iterate → compare)
python demo.py
```

### Common Parameters (`python demo.py --help`)

A full run does dozens of gpt-5.6-luna Vision calls, which is slow and expensive. The following parameters provide faster paths and allow changing the paper, output directory, and models:

| Parameter | Description |
|---|---|
| `--paper PATH` | Path to the input paper Markdown (default `paper/sample_paper.md`). Just replace with your own paper. |
| `--out-dir DIR` | Output directory for artifacts (default `output/`): each round's `slides.md`/`review.json`/`comparison_summary.json`. Rendered PNGs are always in `slidev_workspace/exports/`. |
| `--text-model NAME` | Proposer / single agent text model, **overrides** the `TEXT_MODEL` environment variable (default `gpt-5.6-luna`). |
| `--vision-model NAME` | Reviewer / independent judge image model (must support images), **overrides** the `VISION_MODEL` environment variable (default `gpt-5.6-luna`). |
| `--mode {both,dual,single}` | Run only one scheme (`dual`=Proposer-Reviewer, `single`=single Agent self-review), saving half the time/cost; `both` (default) does cross-scheme comparison. |
| `--max-rounds N` | Maximum iteration rounds per scheme (default 3). `--max-rounds 1` only produces the first version without revision, the fastest **real LLM** smoke test. |
| `--dry-run` | **Offline walkthrough of the Proposer-Reviewer loop**: real rendering of two scripted `slides.md` versions (crowded first draft → split-page revision), using **deterministic heuristic rules** (judging by text volume per page, not Vision LLM) to play the Reviewer, fully demonstrating the "generate → render → review → revise" loop. **Does not call any LLM, no API Key required**. |
| `--smoke` | **Only** verify the Slidev rendering pipeline (render a two-page deck), **does not call any LLM, no API Key required**. The fastest "didn't break the rendering" self-check. |

```bash
python demo.py --smoke                 # No cost, verify Node/Slidev/chromium are available
python demo.py --dry-run               # No cost, offline view of the Proposer-Reviewer loop (real rendering)
python demo.py --mode dual --max-rounds 1   # One real LLM smoke test (requires API Key)
python demo.py --paper my_paper.md --out-dir run_my   # Change paper, change output directory
```

> The two versions of `slides.md` in `--dry-run` are **scripted** (not LLM-generated), and the Reviewer is just a **heuristic rule** that judges crowding by character count, not a Vision LLM — it's only used to run through the loop **structure** without an API Key, producing real rendered PNGs. To see gpt-5.6-luna **actually look at pixels** for review, use `python demo.py` (requires `OPENAI_API_KEY`). Real result of an offline dry-run: first draft 4 pages (pages 2/3/4 judged high severity overcrowded, score=55, pass=False) → split-page revision 18 pages (score=100, pass=True), rendered PNGs in `slidev_workspace/exports/dryrun_round*/`.

## File Descriptions

| File | Description |
|---|---|
| `demo.py` | Main pipeline: run both schemes, independent judge scoring, print token comparison |
| `agents.py` | `Proposer` / `Reviewer` / `SelfReviewAgent` three Agents + `TokenMeter` for measurement |
| `renderer.py` | Call `slidev export --format png` to render `slides.md` into per-page PNGs |
| `make_figures.py` | Reproduce 2 charts from the paper's data using matplotlib, place into Slidev `public/` |
| `paper/sample_paper.md` | Condensed paper (FlashAttention, includes title/sections/tables/results) |
| `package.json` | Slidev and rendering dependencies |
| `output/` | Run artifacts: each round's `slides.md`, `review.json`, `comparison_summary.json` |
| `slidev_workspace/exports/` | PNGs rendered each round (`dual_round1/`, `single_round1/` …) |

## Expected Output Example

After a full run, real artifacts under `output/` and `slidev_workspace/exports/` (excerpt):

```
output/
├── dual_round1_slides.md      # Dual Agent round 1 slidev source (first version intentionally cramped)
├── dual_round1_review.json    # Reviewer's structured suggestions JSON for round 1
├── dual_round2_slides.md      # Round 2 revised based on feedback
├── dual_round2_review.json
├── dual_round3_slides.md
├── single_round1_slides.md    # Single Agent self-review versions
├── single_round2_slides.md
├── single_round3_slides.md
└── comparison_summary.json    # Quality scores for both schemes + token consumption summary

slidev_workspace/exports/
├── dual_round1/1.png … 5.png      # First version rendering: paragraphs too long, chart bottom exceeds page
├── dual_round2/1.png … 8.png      # Revised version: split pages, each page with 8 items cleaner
└── single_round1/1.png …          # Single Agent version renderings
```

> Note: Slidev's PNG export is **one PNG per page** (`1.png`, `2.png`…); this experiment does not produce a single PDF. If PDF is needed, change `--format png` to `--format pdf` in `renderer.py`. `comparison_summary.json` records both schemes' `iteration_scores`, `final_quality`, and `peak_context_prompt_tokens` (peak context), which is the core comparison data in the book.

## How to Adapt / Extend

- **Change model / change provider**: Through environment variables (see `env.example`) or command-line parameters (higher priority), no code changes needed.
  - `OPENAI_API_KEY`: API key (one must be set; if not configured, `OPENROUTER_API_KEY` is used as fallback, automatically switching to OpenRouter).
  - `OPENAI_BASE_URL`: Point to any endpoint compatible with the OpenAI protocol (self-hosted gateway / other providers).
  - `TEXT_MODEL` / `--text-model`: Model used for Proposer / single agent text part (default `gpt-5.6-luna`).
  - `VISION_MODEL` / `--vision-model`: Model used for Reviewer / independent judge image viewing, **must support image input** (default `gpt-5.6-luna`).
- **Change input paper / output directory**: Command line `--paper PATH` specifies the paper, `--out-dir DIR` specifies the artifact directory (no code changes needed); you can also directly replace `paper/sample_paper.md` (just keep the Markdown section structure). If the new paper has its own data charts, modify the plotting functions in `make_figures.py` and update the `{filename: description}` returned by `generate_all()`, and the Proposer will reference these figures based on the description.
- **Slidev rendering dependencies (important)**: The rendering pipeline depends on **Node** + `node_modules/` in this directory, which includes `@slidev/cli`, `playwright-chromium` (underlying browser for `slidev export --format png`), and `typescript` (required for twoslash code highlighting). If `node_modules/` is missing or corrupted, run `npm install` in this directory to reinstall;If the browser binary is not installed, run `npx playwright install chromium` as a fallback. After installation, first run `python demo.py --smoke` to verify the rendering pipeline, then run the full process.

## About "The First Version Is Intentionally Cramped"

To **reliably reproduce** the closed loop of "render → find issues → revise", in `agents.py`, the **first version** of the Proposer / single Agent stuffs the entire paper into about 4 pages, pasting the original text in paragraphs (a common "dump content first" draft approach). This produces **real** text overflow and chart clipping (see `slidev_workspace/exports/dual_round1/2.png`: paragraphs too long, chart bottom exceeds page). The Reviewer's issues are all derived from the vision model (default gpt-5.6-luna) **looking at actual pixels**, and the revisions are also real—not a preset script. If the first version instruction were changed to "directly generate an 8-12 page concise version", the vision model often passes in one round, and the iteration process is lost. Results from one real run (with random variation):

```
Dual Agent: round1 score=85 pass=False (4 medium: p2/p3/p4 overcrowded, p2 image_size)
          → Proposer splits pages and simplifies → round2 score=95 pass=True (+10 improvement)
Peak context: Dual Agent = 9308 tok, Single Agent self-review = 14179 tok (Single Agent image accumulation: 1640→8069→14179)
```

## Limitations

- **Subjective aesthetics**: The Reviewer's preferences may not match the target user's. The feedback loop could converge to a local optimum that the Reviewer approves of but users find cramped (see end-of-book thought question: how to incorporate user preferences into the loop).
- **Chart source**: This experiment does not parse real PDFs. Charts are programmatically reproduced from the paper's figures by `make_figures.py`, serving as stand-ins for the "original paper charts"; integrating real PDFs would require additional image extraction.
- **Cost/time**: Each round, the Reviewer sends about 10 screenshots to the vision model (default gpt-5.6-luna). A single run requires dozens of API calls; screenshots are uniformly scaled to 1280px width to control tokens.
- **Determinism**: LLM and Vision judgments have randomness; specific scores/suggestions vary slightly each time. `temperature` has been lowered, but whether iteration "passes in 1 round" depends on the quality of the first version.
- **Rendering dependency**: `slidev export` depends on playwright-chromium; environments without network access or the ability to install chromium must first resolve the browser binary issue (see "Running" step 2).
