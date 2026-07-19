# Experiment Code Gaps · Resolution Plan (SHIP Priority)

Principle (per author's instruction): **Default SHIP** — every experiment in the book should have a reference implementation and architecture available in the repository for readers to consult. Only write no new code when there is a **specific reason**:

- **ALREADY** — Code already exists somewhere in the repository; only need to fix the pointer in the book/README.
- **KEEP-EXT** — Training-type experiments, core code in an external fork; add a "thin shell" in the repo (pin upstream commit + `run.sh`/config + results table), do not rewrite.
- **SHIP** — Need to create a new runnable reference implementation in the repo (default).

Effort: S (1–2 days) / M (3–5 days) / L (1–2 weeks, usually includes GPU training).

---

## Resolution Summary Table

| Experiment | Name | Status | Resolution | Effort | Notes |
|---|---|---|---|---|---|
| 2-5 | Prompt Injection Attack & Defense | No directory | **SHIP** | S | Minimal attack/defense demo: 3 attack scenarios × 4 defense configurations + success rate statistics |
| 2-6 | Agent Skills Generate PPT | No directory | **SHIP** | S | Runnable script: Claude Code + PPTX Skill wrapper + example input |
| 3-13 | Structured Knowledge Extraction (Judicial) | 🚧 stub | **SHIP** | L | CAIL2018 extraction pipeline + factor importance model + dialogue Agent |
| 4-5 | Asynchronous Agent (Parallel + Interrupt) | 🚧 stub | **SHIP** | M | Design document implementation: parallel tools, interrupt/cancel, state management |
| 5-1 | Code Solves Math (AIME) | No directory | **SHIP** | M | Code sandbox vs. pure CoT accuracy comparison |
| 5-2 | Logic (K&K) | No directory | **SHIP** | S | python-constraint solver |
| 5-3 | Small Model Codification (τ-bench) | No directory | **SHIP** | M | Three-layer guard + expected_* validation |
| 5-4 | Paper → PPT (Slidev) | No directory | **SHIP** | M | proposer-reviewer + Vision-LLM review loop |
| 5-5 | Paper Explanation Video | No directory | **SHIP** | M | TTS + ffmpeg PPT → video |
| 5-6 | Blender Smart Editing | No directory | **SHIP** | M | Blender Python API + two-step scene localization |
| 5-7 | Adaptive Log Parsing | No directory | **SHIP** | M | Failure detection → code generation → browser test → hot reload |
| 5-8 | Production Log Intelligent Diagnosis | No directory | **SHIP** | M | Trace analysis → report → regression test → GitHub issue (MCP) |
| 5-9 | Dynamic Form Intent Clarification | No directory | **SHIP** | M | Agent generates cascading HTML forms |
| 5-10 | ERP Agent (NL → SQL) | No directory | **SHIP** | M | PostgreSQL schema + 10 queries |
| 5-11 | Conversational Interface Customization | No directory | **SHIP** | M | React + FastAPI + HMR |
| 6-5 | TTS Quality Evaluation Pipeline | No directory | **SHIP** | M | Multi-provider generation + Gemini multimodal Rubric review |
| 6-7 | Agent Cost Analysis | No directory | **SHIP** | S | Tracing cost breakdown + KV-cache/compression A/B |
| 6-8 | Multi-Dimensional Model Performance Benchmark | No directory | **SHIP** | M | Throughput/TTFT/p95/availability stress test harness |
| 7-1/7-2 | Treasure Hunt: Q-learning / RL vs LLM | — | **ALREADY** | — | Code in `chapter1/learning-from-experience` (verified) |
| 7-3 | Train LLM from Scratch (MiniMind 2) | 📖 fork | **KEEP-EXT** | S | Code in fork `bojieli/minimind` (QK-Norm+Muon, produces loss curve in README); pin commit 8bdc5d9 |
| 7-4 | Train VLM Yourself (Projection Layer from Scratch) | 📖 fork | **KEEP-EXT** | S | Code in fork `bojieli/minimind-v` (CLIP+LLM → train projector from scratch → SFT, 26M VLM, produces README results); pin commit ead791c. Note: `SFTvsRL/sft` is another type of VLM experiment (fine-tune full Llama-3.2-Vision, corresponds to 7-11/7-12) |
| 7-9 | CoT Distillation [Extended] | No directory | **SHIP** | M | Rule validator filtering + distillation + three-step acceptance |
| 7-10 | AdaptThink | 📖 ext | **KEEP-EXT** | M | Pin `AdaptThink-original` commit + results table |
| 7-11/7-12 | GeneralPoints / V-IRL | — | **ALREADY** | — | Code in `chapter7/SFTvsRL` (includes `gym_virl`) |
| 7-13 | SimpleVLA-RL [Extended] | 📖 ext | **KEEP-EXT** | M | Rollouts already exist; pin upstream + results table |
| 7-14 | RLVP Reward Results Penalize Paths [Extended] | No directory | **SHIP** | L(GPU) | Biggest gap: book uses author's own paper numbers but zero code; must release training/evaluation |
| 7-15 | ReTool | 📖 ext | **KEEP-EXT** | M | verl fork; pin commit + run.sh + results table |
| 7-16 | AWorld-train Sandbox RL | 📖 ext | **KEEP-EXT** | S | Pin commit only (no numerical claims) |
| 8-3 | System Prompt Automatic Optimization | No directory | **SHIP** | M | Automatic optimization on tau-bench + comparison |
| 8-4 | Active Tool Discovery (120+ Tools) | No directory | **SHIP** | M | Core argument of Chapter 8 |
| 8-5 | Alita-style Web Tool Finding Self-Evolution | No directory | **SHIP** | M | Core argument of Chapter 8 |
| 8-6 | Self-Evolution Evaluation Dataset | No directory | **SHIP** | S | 20 tasks, four-layer validation |
| 9-2 | PineClaw Phone Agent | No directory | **SHIP** | M | pine-voice SDK + make_phone_call tool ReAct Agent |
| 9-3 | Step-Audio R1 End-to-End | No directory | **SHIP** | S | End-to-end voice reasoning demo (Table 9-1 numbers add reference footnote separately) |
| 9-4 | Qwen2-Audio Streaming Perception | No directory | **SHIP** | S | Chunked recognition latency comparison demo |
| 9-5 | Fish Audio Control Token TTS | No directory | **SHIP** | S | 12 reference voice library + control token mapping demo |
| 10-1 | Phased System Prompt | No directory | **SHIP** | S | Three-phase role switching: requirements/implementation/review |
| 10-2 | Multi-Role transfer_to_agent | No directory | **SHIP** | S | Five roles + transfer_to_agent tool |
| 10-3 | Book Translation Agent | No directory | **SHIP** | M | Manager/Glossary/Translation/Proofreading four Agents |
| 10-4/10-5 | Phone + Computer Dual Agent | 📦 pointer | **KEEP-EXT** | — | Already points to `19PINE-AI/TalkAct` (complete) |
| 10-6 | Multi-Site Parallel Collection | No directory | **SHIP** | M | 10 Agents + message bus + cascading termination |
| 10-8 | Voice Werewolf | No directory | **SHIP** | L | Judge + information permission control + real-time voice multi-Agent |

---

## Summary

- **SHIP (approx. 28)**: Write new reference implementations. Among them:
  - Lightweight S (approx. 10): 2-5, 2-6, 5-2, 6-7, 8-6, 9-3, 9-4, 9-5, 10-1, 10-2 — recommended to do first (quick wins).
  - Medium M (approx. 16): 5-1, 5-3~5-11, 6-5, 6-8, 7-9, 8-3, 8-4, 8-5, 9-2, 10-3, 10-6, 4-5.
  - Heavy L/GPU (2): 3-13, 7-14, 10-8.
- **KEEP-EXT (8)**: 7-3 (`bojieli/minimind`), 7-4 (`bojieli/minimind-v`), 7-10, 7-13, 7-15, 7-16, 10-4, 10-5 — pin commit + results table, do not rewrite.
- **ALREADY (2 groups)**: 7-1/7-2 (`chapter1/learning-from-experience`), 7-11/7-12 (`chapter7/SFTvsRL`) — only fix pointers and naming.

## Suggested Build Order (Batches)

1. **Batch 1 · Multi-Agent Self-Contained (S/M, no external dependencies, high pedagogical value)**: 10-1, 10-2, 10-3, 10-6, 4-5.
2. **Batch 2 · Chapter 8 Core Self-Evolution**: 8-4, 8-5, 8-3, 8-6.
3. **Batch 3 · Chapter 5 Coding Agent Applications**: 5-1, 5-3 first, then the rest 5-2/5-4~5-11.
4. **Batch 4 · Chapters 6/9 Evaluation and Voice Demos**: 6-5, 6-7, 6-8, 9-2~9-5.
5. **Batch 5 · Training Type**: KEEP-EXT thin shells (7-10/13/15/16) → GPU training (7-3, 7-14) → 3-13, 10-8.

## Pending Decisions (Need Author's Approval)

1. ~~7-4 VLM~~ **Resolved**: Code for training projection layer from scratch is fork `bojieli/minimind-v` (26M VLM), same origin as 7-3's `bojieli/minimind`. Follow KEEP-EXT with clone instructions.
2. **7-14 RLVP**: RLVP is the paper at github.com/19PINE-AI/rlvp; just use a README reference.
3. **Orphan stub directories**: `chapter8/feedback-guided-sampling`, `learn-from-observation` — delete.
