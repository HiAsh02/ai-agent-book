"""
Experiment 9-4 companion demo: end-to-end speech reasoning vs. cascaded pipeline (run both paths and compare).

The core of Experiment 9-4 in the book is the end-to-end speech reasoning model Step-Audio R1 (directly "listen → think → speak").
Step-Audio R1 requires multi-GPU deployment and has no public endpoint, so this demo uses OpenAI's
speech-to-speech model `gpt-audio` as a **real runnable end-to-end representative** (audio in, single model,
audio out, no separate ASR/LLM/TTS stages), compared with the **cascaded baseline** (whisper-1 → gpt-5.6-luna → tts-1)
on the same problem. The latencies of both paths are measured in real time, and both output audio files are verified with ffprobe.

Flow:
  1. Use TTS to synthesize a "user question" speech (a math problem requiring multi-step reasoning, Spoken-MQA style),
     as the common input for both pipelines;
  2. End-to-end: one gpt-audio call, audio in → speech answer + transcription out (single model fusion);
  3. Cascaded: whisper-1 transcription → gpt-5.6-luna reasoning → tts-1 synthesis of answer speech (three stages in series);
  4. Print the real latency comparison of both paths, and use ffprobe to confirm that both output audio files are actually generated;
  5. Provide a paradigm comparison of end-to-end vs. cascaded (latency, paralinguistic information loss), and reference Table 9-1 in the book.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from speech_model import (
    CascadedSpeechModel,
    EndToEndSpeechModel,
    PipelineResult,
    synthesize_question_audio,
)

HERE = Path(__file__).parent
AUDIO_DIR = HERE / "audio"

#A spoken math problem requiring multi-step reasoning (Spoken-MQA style: first understand, then multi-step calculation)
USER_QUESTION = (
    "Xiao Ming has 12 yuan. He buys 3 pencils, each costing 2 yuan,"
    "and then uses the remaining money to buy as many erasers as possible, each costing 1.5 yuan."
    "How much money does he have left in the end?"
)

#A sentence where "the answer depends on how it is said": literally it is compliant/indifferent, but the true emotion can only be judged by tone, speed, and intonation
#to determine (whether it is truly no objection, or helplessness, or sulking). This type of paralinguistic task is exactly
#the watershed between end-to-end and cascaded—see chapter9.md "Text Agent Thinking" and MGRD.
PARALINGUISTIC_QUESTION = "Alright, whatever, I have no opinion."

#Two types of tasks, corresponding to the two comparison axes in the book:
#   math          —— semantic task: cascaded and end-to-end have comparable accuracy (Book 9.3 "Self-Cascading" section), mainly compare latency.
#   paralinguistic—— paralinguistic task: the answer depends on "how it is said". Cascaded compresses speech into plain text at ASR,
#                    LLM can only guess emotion from literal words ("Text Agent Thinking" in the book); end-to-end directly hears acoustic features.
TASKS: dict[str, dict] = {
    "math": {
        "question": USER_QUESTION,
        "e2e_prompt": (
            "You are a Chinese voice assistant. Please first complete the necessary reasoning internally, then output the conclusion in concise, colloquial,"
            "speech-friendly Chinese, within three sentences."
        ),
        "cascade_prompt": (
            "You are a voice assistant. Please first perform necessary reasoning, then give a concise, colloquial,"
            "speech-friendly Chinese answer. The answer should be within three sentences."
        ),
        "axis": (
            "Semantic (Spoken-MQA style): the answer depends only on \"what is said\". Cascaded and end-to-end have comparable accuracy,"
            "this task mainly compares the [latency] dimension."
        ),
    },
    "paralinguistic": {
        "question": PARALINGUISTIC_QUESTION,
        "e2e_prompt": (
            "You are a Chinese voice assistant. Please first judge the speaker's emotion, speed, and intonation (try to rely on acoustic features"
            "themselves, not just literal meaning), state the tone you hear, then give a considerate, colloquial,"
            "speech-friendly Chinese response, within three sentences."
        ),
        "cascade_prompt": (
            "You are a Chinese voice assistant. Please first judge the speaker's emotion, speed, and intonation, state the tone you hear,"
            "then give a considerate, colloquial, speech-friendly Chinese response, within three sentences."
        ),
        "axis": (
            "Paralinguistic: the answer depends on \"how it is said\". The LLM in cascaded only gets the ASR plain"
            "text, any emotion judgment is \"Text Agent Thinking\" (guessing from literal words); end-to-end directly hears acoustic features."
            "This task compares the [information loss] dimension. Note: the default input is synthesized by TTS, emotion is flat, differences are weakened;"
            "use --audio-input to feed a real emotional recording, the contrast will be much more obvious."
        ),
    },
}


def hr(char: str = "-", n: int = 68) -> str:
    return char * n


def ffprobe_info(audio_path: str) -> dict:
    """Use ffprobe to read the actual audio information (duration, format, bitrate) to confirm the file has been generated."""
    if not shutil.which("ffprobe"):
        return {"error": "ffprobe not installed, skip audio verification (brew install ffmpeg)"}
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,format_name,bit_rate,size",
                "-of", "json", audio_path,
            ],
            capture_output=True, text=True, check=True,
        )
        fmt = json.loads(out.stdout).get("format", {})
        return {
            "Format": fmt.get("format_name"),
            "Duration (s)": round(float(fmt.get("duration", 0)), 2),
            "Bitrate (bps)": fmt.get("bit_rate"),
            "File size (bytes)": fmt.get("size"),
        }
    except Exception as e:  # noqa: BLE001
        return {"error": f"ffprobe failed: {e}"}


def print_e2e_result(result: PipelineResult, backend: str) -> None:
    s = result.stages[0]
    print(hr("="))
    print(f"Paradigm 1: End-to-end speech reasoning (backend={backend}, model={s.model}）")
    print(hr("="))
    print("Form: audio in → single model 'listen→think→speak' → audio out (single call, no separate ASR/LLM/TTS stages)")
    print(f"\n[Single-stage] {s.name}  |  Latency={s.latency_s:.2f}s")
    if s.text is not None:
        print(f"    Speech answer transcription (model produces incidentally, not an intermediate text stage):{s.text}")
    print(f"    Speech answer:{s.audio_path}")
    print(f"    ffprobe verification:{ffprobe_info(s.audio_path)}")
    print(f"\nEnd-to-end total latency (single model forward pass):{result.total_latency_s:.2f}s")


def print_cascade_result(result: PipelineResult) -> None:
    print("\n" + hr("="))
    print(f"Paradigm 2 (baseline): Cascaded pipeline ASR → LLM → TTS")
    print(hr("="))
    for i, s in enumerate(result.stages, 1):
        print(f"\n[Stage {i}] {s.name}  |  Model={s.model}  |  Latency={s.latency_s:.2f}s")
        if s.text is not None:
            print(f"    Text:{s.text}")
        if s.audio_path is not None:
            print(f"    Audio:{s.audio_path}")
            print(f"    ffprobe verification:{ffprobe_info(s.audio_path)}")
    print(f"\nCascaded total latency (serial sum of stages):{result.total_latency_s:.2f}s")


def print_comparison(e2e: PipelineResult, e2e_backend: str, cas: PipelineResult,
                     task: str) -> None:
    """Print the real comparison of end-to-end vs cascaded (measured latency) + paradigm conceptual differences + Table 9-1 from the book (reference)."""
    stages = {s.name: s for s in cas.stages}
    asr = stages["ASR speech recognition"]
    llm = stages["LLM reasoning"]
    tts = stages["TTS speech synthesis"]

    print("\n" + hr("="))
    print("End-to-end vs cascaded: real comparison")
    print(hr("="))
    print(f"\n[Task]{task}：{TASKS[task]['axis']}")
    print("\n[1] Measured total latency (this run, subject to network and load fluctuations)")
    print(f"    End-to-end ({e2e_backend}, single model call):{e2e.total_latency_s:.2f}s")
    print(f"    Cascaded ASR({asr.latency_s:.2f}s) + LLM({llm.latency_s:.2f}s) "
          f"+ TTS({tts.latency_s:.2f}s) = {cas.total_latency_s:.2f}s (three-segment serial accumulation)")
    delta = cas.total_latency_s - e2e.total_latency_s
    faster = "End-to-end is faster" if delta > 0 else "Cascade is faster"
    print(f"    Difference: {abs(delta):.2f}s（{faster}). Note that end-to-end means \"one forward pass for the entire audio segment\"."
          "True streaming end-to-end can also \"think while speaking\" to further reduce the latency of the first character; the three segments of cascade are naturally accumulated serially.")

    print("\n【2】Information Loss (Paralinguistics / Tone) — Paradigm difference, not this demo's latency")
    print("    Cascade compresses speech into plain text at the ASR stage, losing almost all of the speaker's emotion, speaking rate, intonation, stress, pauses,")
    print("    and background ambient sounds/music during the handover — the LLM only sees \"what was said\", not \"how it was said\".")
    print("    The input speech in this demo is flattened to plain text at the ASR stage:")
    print(f"        ASR text → \"{asr.text}」")
    print("    End-to-end models directly transmit these paralinguistic cues in the latent space, enabling perception of")
    print("    emotion/speaking rate/intonation, and generating expressive, prosody-matched responses accordingly.")
    print("    Responses of the two paths to the same audio segment (intuitively compare whether \"how it was said\" is heard):")
    print(f"        Cascade (relying only on ASR text, text agent reasoning) → \"{llm.text}」")
    print(f"        End-to-end (directly listening to acoustic features)        → \"{e2e.stages[0].text}」")

    print("\n【3】Table 9-1 in the book: Step-Audio R1 different voice thinking configurations (cited from the Step-Audio R1 paper,"
          "not produced by this demo)")
    print("    Configuration                          Spoken-MQA   URO-Bench")
    print("    Answer directly without thinking (baseline)           70.6%        77.4")
    print("    MPS Speak-First (zero latency)        92.8%        82.5")
    print("    MPS Think-First (~80 tok latency)  93.9%        84.8")
    print("    Full TBS (no latency constraint)           93.0%         —")
    print("    Source: Step-Audio R1 paper (cited from Table 9-1 in the book). These are evaluation scores reported in the paper,")
    print("not produced by this demo — this demo only outputs the real latency in 【1】 above and two real audio clips.")
    print("    Key point: Speak-First hardly degrades reasoning accuracy (92.8% ≈ TBS 93.0%), because the beginning of CoT")
    print("    often just restates the question; this is why end-to-end \"think while speaking\" achieves low latency without losing accuracy.")

    print("\n【4】Trade-off Summary")
    print("    Cascade: clear modules, each can be independently tuned, good interpretability; but latency accumulates serially, and paralinguistic loss is large.")
    print("    End-to-end: lower latency, retains non-textual information, natural prosody; the cost is large training data requirements,")
    print("            Poor interpretability. The two will coexist for a long time in production systems in 2026.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="demo.py",
        description="Experiment 9-4: End-to-end speech thinking vs cascaded pipeline. Synthesize (or read) a segment of \"user"
                    "question\" speech, run both end-to-end (gpt-audio, can switch to Step-Audio R1) and cascaded"
                    "(whisper-1 → gpt-5.6-luna → tts-1) on the same topic, and print real latency and information loss comparison.",
        epilog="Example: \n"
               "  python demo.py                               # Default: math problem, end-to-end + cascaded comparison\n"
               "  python demo.py --task paralinguistic         # Paralinguistic task: highlight end-to-end advantage\n"
               "  python demo.py --audio-input my_voice.wav    # Use real recording as input (better reflects tone differences)\n"
               "  python demo.py --e2e-model gpt-audio --voice nova --output-dir out\n"
               "  python demo.py --step-audio-endpoint http://localhost:8000/v1/audio/chat",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--task", choices=sorted(TASKS), default="math",
                   help="Task type: math=oral math problem (semantic task, mainly latency);"
                        "paralinguistic=paralinguistic task (answer depends on \"how it is said\", highlighting end-to-end"
                        "advantage over cascaded). Default math.")
    p.add_argument("--question", default=None,
                   help="Custom oral question text, overrides the default question for --task. Mutually exclusive with --audio-input.")
    p.add_argument("--audio-input", metavar="FILE", default=None,
                   help="Directly use an existing audio file (.wav/.mp3) as input, skipping TTS synthesis"
                        "of the question; suitable for feeding real emotional recordings. Mutually exclusive with --question.")
    p.add_argument("--e2e-model", default=None,
                   help="End-to-end speech-to-speech model name (default: environment variable E2E_MODEL,"
                        "then default gpt-audio).")
    p.add_argument("--step-audio-endpoint", default=None,
                   help="Self-deployed Step-Audio R1 service address; if given, the end-to-end path uses it"
                        "(overrides environment variable STEP_AUDIO_ENDPOINT).")
    p.add_argument("--voice", default="alloy",
                   help="Voice for answer audio (shared by end-to-end and cascaded TTS, default alloy).")
    p.add_argument("--output-dir", metavar="DIR", default=None,
                   help="Audio output directory (default: audio/ in the same directory as the script).")
    p.add_argument("--skip-cascade", action="store_true",
                   help="Run only end-to-end, do not run cascaded comparison baseline.")
    args = p.parse_args()
    if args.question and args.audio_input:
        p.error("--question and --audio-input are mutually exclusive, please choose one.")
    return args


def _map_openrouter_model(model: str) -> str:
    """Map common model names to OpenRouter's provider/model format."""
    if "/" in model:
        return model
    if model.startswith("gpt-"):
        return "openai/" + model
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"


def _resolve_llm_client(openai_client: OpenAI):
    """Route selection for cascaded pure-text LLM inference: prefer OpenRouter, otherwise fall back to OpenAI direct connection.

    Returns (client, model, route_label). ASR/TTS/end-to-end audio still uses openai_client.
    """
    model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.6-luna"
    if os.getenv("OPENROUTER_API_KEY"):
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            timeout=120.0,
            max_retries=3,
        )
        return client, _map_openrouter_model(model), "OpenRouter"
    return openai_client, model, "OpenAI direct connection"


def main() -> int:
    args = parse_args()
    task = args.task
    task_cfg = TASKS[task]
    question = args.question or task_cfg["question"]

    load_dotenv(HERE / ".env")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not configured. End-to-end gpt-audio and cascaded ASR(whisper)/TTS(tts-1) "
              "are all audio endpoints, only available via OpenAI direct connection—OpenRouter has no audio endpoints, so this experiment must provide"
              " an OpenAI direct connection Key. Please copy env.example to .env and fill it in.", file=sys.stderr)
        return 1

    # Audio client: end-to-end gpt-audio, cascaded whisper/tts must all use OpenAI direct connection.
    # timeout + automatic retry: a single network/SSL glitch should not crash the entire pipeline.
    client = OpenAI(api_key=api_key, timeout=120.0, max_retries=3)

    #  Cascading intermediate pure text LLM thinking: prioritize OpenRouter (bypass the organization real-name authentication of direct gpt-5.6* connection),
    #  fall back to the above OpenAI direct client when OPENROUTER_API_KEY is not set.
    llm_client, llm_model, llm_route = _resolve_llm_client(client)
    out_dir = Path(args.output_dir) if args.output_dir else AUDIO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    e2e_audio = str(out_dir / "answer_end_to_end.wav")
    cascade_audio = str(out_dir / "answer_cascade.mp3")

    # -- Step 1: Prepare the "user question" voice (common input for two pipelines) ----------------------
    print(hr("="))
    print(f"Step 1: Prepare a \"user question\" voice (task={task}, as common input for the two pipelines)")
    print(hr("="))
    if args.audio_input:
        question_audio = args.audio_input
        if not Path(question_audio).is_file():
            print(f"Error: The audio file specified by --audio-input does not exist:{question_audio}",
                  file=sys.stderr)
            return 1
        print(f"Use existing input audio (skip TTS synthesis):{question_audio}")
        print("Question text: (unknown, from audio file, will be restored by cascading ASR transcription)")
    else:
        question_audio = str(out_dir / "user_question.mp3")
        print(f"Question text:{question}")
        synthesize_question_audio(client, question, question_audio)
        print(f"Input audio synthesized by TTS:{question_audio}")
    print(f"ffprobe check:{ffprobe_info(question_audio)}")

    # -- Step 2: End-to-end voice thinking (real run) -----------------------------------
    print("\n" + hr("="))
    print("Step 2: End-to-end voice thinking (audio in → single model → audio out)")
    print(hr("="))
    e2e_model = EndToEndSpeechModel(
        client,
        model=args.e2e_model,
        voice=args.voice,
        system_prompt=task_cfg["e2e_prompt"],
        endpoint=args.step_audio_endpoint,
    )
    backend = e2e_model.backend
    if backend == "step-audio-r1":
        print(f"Detected STEP_AUDIO_ENDPOINT={e2e_model.endpoint}, use real Step-Audio R1.")
    else:
        print(f"STEP_AUDIO_ENDPOINT not configured, use OpenAI speech-to-speech model "
              f"{e2e_model.model} as the end-to-end representative (real audio → single model → audio).")
        print("If you want to replace it with the Step-Audio R1 from the book, deploy it yourself and write the address into STEP_AUDIO_ENDPOINT.\n")
    try:
        e2e_result = e2e_model.run(question_audio, e2e_audio)
    except Exception as e:  # noqa: BLE001
        print(f"Error: End-to-end call failed:{e}", file=sys.stderr)
        return 2
    print_e2e_result(e2e_result, backend)

    # -- Step 3: Cascading pipeline (baseline for comparison) ---------------------------------------
    cascade_result = None
    if not args.skip_cascade:
        print(f"\nCascading LLM thinking routing:{llm_route} (model {llm_model}）；"
              f"ASR/TTS still use OpenAI direct connection.")
        cascaded = CascadedSpeechModel(
            client,
            llm_model=llm_model,
            tts_voice=args.voice,
            system_prompt=task_cfg["cascade_prompt"],
            llm_client=llm_client,
        )
        cascade_result = cascaded.run(question_audio, cascade_audio)
        print_cascade_result(cascade_result)

    # -- Step 4: Real latency comparison + paradigm differences + Table 9-1 (reference) ---------------------
    if cascade_result is not None:
        print_comparison(e2e_result, backend, cascade_result, task)

    print("\nDone. Listen:")
    print(f"  ffplay {e2e_audio}      # End-to-end voice answer")
    if cascade_result is not None:
        print(f"  ffplay {cascade_audio}   # Cascading voice answer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
