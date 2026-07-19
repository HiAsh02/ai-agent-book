# Experiment 2-6: Generating a Presentation from a Paper Using Agent Skills

Accompanying experiment 2-6 (★★) from Chapter 2 of "Deep Understanding of AI Agents" – "Dynamic Prompts and Agent Skills".

## Purpose

Validate the core proposition of the book: **An Agent can complete complex tasks by loading specialized domain Skills on demand through "Progressive Disclosure," without needing to cram all knowledge into the system prompt at once.**

This demo has an Agent generate an 8-12 page PowerPoint from a (bundled) condensed paper. The Agent starts with **only a thin Skill catalog**. Only after it identifies that the task requires the `pptx` Skill does it progressively load that Skill's full workflow, sub-documents, and bundled scripts, finally generating a real `.pptx` file using **python-pptx**.

## Relationship with the Anthropic PPTX Skill

The original experiment in the book runs on **Claude Code + the official Anthropic PPTX Skill**. Since the Anthropic key for the current environment is invalid, this project **builds its own isomorphic Skills mechanism** to reproduce the same concept, rather than calling Anthropic:

| Dimension | Anthropic PPTX Skill (in book) | This Project (Self-built Isomorphic Version) |
|-----------|-------------------------------|----------------------------------------------|
| Runtime | Claude Code | Python + OpenAI SDK (`gpt-5.6-luna`) |
| Layer 1 · Metadata | Inject all Skill names+descriptions at startup | `scan_skill_catalog()` reads only frontmatter, appends to system prompt |
| Layer 2 · Core Workflow | Skill tool loads the full `SKILL.md` | `read_skill` tool loads `skills/pptx/SKILL.md` |
| Layer 3 · Details | References `html2pptx.md` / `reference.md` | `read_skill_file` reads `reference.md` / script source code |
| Bundled Scripts | `scripts/thumbnail.py`, etc. | `scripts/generate_pptx.py` (python-pptx generator) |

The mechanisms correspond one-to-one, simply replacing "Claude's built-in Skill loader" with several explicit read/execute tools. This allows a genuine demonstration of the three-layer progressive disclosure process without requiring Anthropic access.

> Note: This project primarily uses OpenAI (default model gpt-5.6-luna). **General fallback**: If `OPENAI_API_KEY` is not set, as long as `OPENROUTER_API_KEY` is configured, it will automatically switch to OpenRouter (`gpt-*` maps to `openai/…`). Behavior is completely unchanged when `OPENAI_API_KEY` is set.

## Three-Layer Structure of Progressive Disclosure

```
skills/
└── pptx/
    ├── SKILL.md              # Layer 1: Top YAML frontmatter (name+description) – Only this enters the system prompt
    │                         # Layer 2: Core workflow in the body – Loaded only when read_skill is called
    ├── reference.md          # Layer 3: Layout/color/technical details – Loaded only when read_skill_file is called
    └── scripts/
        └── generate_pptx.py  # Bundled executable script – Executed only when run_skill_script is called
```

- **Layer 1 (Metadata)**: At Agent startup, the `system prompt` contains only each Skill's `name + description` (a few hundred tokens). At this point, it doesn't know how to make a PPT.
- **Layer 2 (Core Workflow)**: The Agent determines the task needs `pptx`, calls `read_skill("pptx")` to load the full `SKILL.md` as a tool result into the context, obtaining the slide sequence plan and script invocation conventions.
- **Layer 3 (Details)**: If implementation/style details are needed, the Agent uses `read_skill_file("pptx", "reference.md")` or reads the script source code.
- **Execution**: The Agent organizes the slide outline JSON, calls the bundled `generate_pptx.py` via `run_skill_script`, and uses python-pptx to produce `output/presentation.pptx`.

## Running

```bash
pip install -r requirements.txt
cp env.example .env        # Or directly export
export OPENAI_API_KEY=sk-...   # Default model gpt-5.6-luna, can be overridden with OPENAI_MODEL
python demo.py
python demo.py --paper papers/your_paper.md    # Use a different paper/outline
python demo.py -o output/deck.pptx --model gpt-5.6-luna   # Specify output path / model
python demo.py --help                          # View all parameters
```

A single command `python demo.py` runs the full process: it makes a real call to OpenAI, prints each step of progressive disclosure, generates `output/presentation.pptx`, and reopens the file with python-pptx to read back the page count and each page's title for validation.

### Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--paper` | `papers/sample_paper.md` | Input paper/outline (markdown) path |
| `--output` / `-o` | `output/presentation.pptx` | Output `.pptx` path |
| `--model` | `OPENAI_MODEL` or `gpt-5.6-luna` | OpenAI model name |
| `--max-turns` | `8` | Maximum turns for the agentic loop |
| `--offline` | Off | Offline demo, does not call OpenAI (see below) |

### Offline Mode (No API Key Required, Reproducible)

Without an OpenAI key, use `--offline` to run the same three-layer progressive disclosure: it reads the built-in outline `papers/sample_outline.json`, goes through **the exact same tool channels as the online version** (`read_skill` → `read_skill_file` → `run_skill_script`), and deterministically generates and validates the pptx. The only difference is that "which Skill to use" and "what the outline contains" are given by pre-set files, rather than decided by the model in real-time. Therefore, it is suitable as a reproducible teaching demo and smoke test.

```bash
python demo.py --offline                       # Generates output/presentation.pptx, no network required
python demo.py --offline -o output/deck.pptx   # Specify output path
```

The bundled script can also run independently of the Agent, directly converting an outline JSON to pptx:

```bash
python skills/pptx/scripts/generate_pptx.py papers/sample_outline.json output/deck.pptx
```

## Real Run Output (Excerpt)

```
[Layer 1 · Metadata] Agent starts with only this thin Skill catalog (system prompt):
== Installed Skills (Thin Catalog, Metadata Only) ==
- pptx: Generate PowerPoint from paper... Use when... Don't use when...

[Agent Round 1] Tool call -> read_skill(name=pptx)
  >>> [Progressive Disclosure · Layer 2] Loading full SKILL.md (1150 characters)
[Agent Round 2] Tool call -> read_skill_file(name=pptx, path=scripts/generate_pptx.py)
  >>> [Progressive Disclosure · Layer 3] Loading sub-document (4270 characters)
[Agent Round 3] Tool call -> run_skill_script(name=pptx, script=generate_pptx.py, ...)
  >>> Generating presentation.pptx ...

[Validation] Reopening the generated file with python-pptx, reading page count and titles:
Total pages: 9
  Page  1 title: Condensed Paper: The Impact of Progressive Disclosure Agent Skills on Context Efficiency
  Page  2 title: Table of Contents
  Page  3 title: Research Background and Problem
  Page  4 title: Method Overview (General Approach)
  ...
  Page  9 title: Summary
Validation passed: This is a valid .pptx (9 pages) that can be opened by python-pptx / PowerPoint.
```

(The page count and titles are planned by the model in real-time and may vary slightly between runs, but will always fall within the 8-12 page range.)

## File Descriptions

| File | Purpose |
|------|---------|
| `demo.py` | Main program: scan thin catalog → agentic loop → progressive disclosure → generate and validate pptx |
| `skills/pptx/SKILL.md` | pptx Skill: frontmatter (metadata) + core workflow |
| `skills/pptx/reference.md` | Layer 3 details: layout/color/python-pptx technical points |
| `skills/pptx/scripts/generate_pptx.py` | Bundled generator, uses python-pptx to create .pptx from an outline |
| `papers/sample_paper.md` | Bundled condensed paper/outline (online mode input) |
| `papers/sample_outline.json` | Built-in slide outline (offline mode input, also serves as a payload schema example) |
| `output/presentation.pptx` | Generated presentation (output, created after running) |

## Using a Different Paper

Replace `papers/sample_paper.md` with your own paper/outline (markdown), or simply specify the path directly with `python demo.py --paper your_paper.md`.
