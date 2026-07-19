"""Experiment 6-5: Fully Automated TTS Quality Evaluation Pipeline — Run with a Single Command.

    python demo.py                      # Default 4 OpenAI configs x 4 utterances
    python demo.py --providers openai,minimax   # Cross-provider horizontal comparison
    python demo.py --text '一段话'       # Custom text
    python demo.py --gemini             # Use Gemini multimodal to directly listen to audio for evaluation (requires GEMINI_API_KEY)
    python demo.py --quick              # Use only first 2 utterances for quick smoke test
    python demo.py --list-providers     # Offline: view providers and configuration status
    python demo.py --dump-rubric        # Offline: view Rubric dimension definitions

Pipeline: multi-provider TTS synthesis -> ffprobe duration -> Whisper back-transcription -> CER/character accuracy
      -> LLM/Gemini Rubric scoring -> print per-item details + configuration comparison summary table.
Idempotent: audio written to output/ and reused (unless --fresh). Full parameters see `python demo.py --help`.
"""

import argparse
import json
import os
import sys
import time
import traceback
from statistics import mean

import config
import pipeline

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def load_env():
    """Minimal .env loading (no third-party dependencies)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def audio_path(cfg_name: str, sample_id: str) -> str:
    return os.path.join(OUT_DIR, f"{cfg_name}__{sample_id}.mp3")


def evaluate_one(cfg, sample, use_gemini: bool, fresh: bool,
                 judge_model: str = None) -> dict:
    """Run the full pipeline for a single (config, utterance). On any step failure, return error record without throwing."""
    rec = {"config": cfg.name, "sample": sample.id, "challenge": sample.challenge,
           "provider": getattr(cfg, "provider", "openai"), "ok": False, "error": None}
    path = audio_path(cfg.name, sample.id)
    try:
        # 1) Synthesis (idempotent: reuse if exists and not fresh)
        if fresh or not os.path.exists(path) or os.path.getsize(path) == 0:
            pipeline.synthesize(cfg, sample.text, path)
        # 2) Duration
        dur = pipeline.probe_duration(path)
        # 3) Back-transcription
        hyp = pipeline.transcribe(path)
        # 4) CER / Character accuracy
        er = pipeline.char_error_rate(sample.text, hyp)
        # 5) Rubric scoring
        if use_gemini:
            rub = pipeline.judge_gemini_audio(sample.text, sample.emotion, path)
        else:
            rub = pipeline.judge_rubric(sample.text, sample.emotion, hyp, dur, er.cer,
                                        model=judge_model)
        rec.update({
            "ok": True, "duration": dur, "hypothesis": hyp,
            "cer": er.cer, "accuracy": er.accuracy,
            "speed": (er.ref_len / dur) if dur else 0.0,
            "scores": rub.scores, "reasons": rub.reasons,
        })
    except Exception as e:  #Single item failure does not affect the whole table
        rec["error"] = f"{type(e).__name__}: {e}"
    return rec


def fmt(x, nd=2):
    return f"{x:.{nd}f}" if isinstance(x, (int, float)) else str(x)


def print_detail(rec, sample_text):
    head = f"[{rec['config']} | {rec['sample']}] {rec['challenge']}"
    if not rec["ok"]:
        print(f"  {head}\n    !! Failed: {rec['error']}")
        return
    print(f"  {head}")
    print(f"    Original: {sample_text}")
    print(f"    Back-transcription: {rec['hypothesis']}")
    print(f"    Duration: {fmt(rec['duration'])}s   Speed: {fmt(rec['speed'])} chars/sec"
          f"   CER: {fmt(rec['cer'],3)}   Character accuracy: {fmt(rec['accuracy']*100,1)}%")
    s, r = rec["scores"], rec["reasons"]
    for dim in pipeline.RUBRIC_DIMENSIONS:
        print(f"    {dim:<4}: {s.get(dim,'-')}/5  {r.get(dim,'')}")


def summarize(records):
    """Aggregated by config: average CER, average character accuracy, average scores per Rubric dimension, success count."""
    by_cfg = {}
    for rec in records:
        by_cfg.setdefault(rec["config"], []).append(rec)
    rows = []
    for cfg_name, recs in by_cfg.items():
        ok = [r for r in recs if r["ok"]]
        row = {"config": cfg_name, "n_ok": len(ok), "n": len(recs)}
        if ok:
            row["cer"] = mean(r["cer"] for r in ok)
            row["accuracy"] = mean(r["accuracy"] for r in ok)
            for dim in pipeline.RUBRIC_DIMENSIONS:
                row[dim] = mean(r["scores"].get(dim, 0) for r in ok)
        rows.append(row)
    # Sorted by overall score descending, CER ascending
    rows.sort(key=lambda x: (-x.get("Overall", 0), x.get("cer", 1)))
    return rows


def print_table(rows):
    cols = ["Overall", "Clarity", "Naturalness", "Pause Rhythm"]
    header = (f"{'Config':<18}{'Success':>6}{'Character accuracy':>10}{'CER':>8}"
              + "".join(f"{c:>9}" for c in cols))
    print(header)
    print("-" * 74)
    for r in rows:
        ok_str = f"{r['n_ok']}/{r['n']}"
        if not r.get("n_ok"):
            print(f"{r['config']:<18}{ok_str:>6}   (All failed)")
            continue
        acc = f"{r['accuracy']*100:.1f}%"
        line = f"{r['config']:<18}{ok_str:>6}{acc:>10}{r['cer']:>8.3f}"
        line += "".join(f"{r.get(c,0):>9.2f}" for c in cols)
        print(line)


def print_providers():
    """Print all available TTS providers and their configuration status offline (no API key required)."""
    print("Available TTS providers (in book: OpenAI / ElevenLabs / Fish Audio / Minimax / Doubao): \n")
    for key, p in config.PROVIDERS.items():
        state = "Configured" if p.configured() else "Not configured"
        env = " + ".join(p.env)
        print(f"  [{key}]  {p.label}   ({state}; need {env})")
        print(f"      {p.note}")
    print("\nUse --providers openai,minimax to select cross-provider horizontal comparison (default only OpenAI).")
    print("Non-OpenAI providers require their own keys (see env.example); if a key is missing, that row is marked as failed without interrupting the entire table.")


def print_rubric():
    """Print Rubric dimension definitions offline (no API key required)."""
    print("TTS quality evaluation Rubric (1-5 scale, 5 is best):\n")
    for dim in pipeline.RUBRIC_DIMENSIONS:
        print(f"  {dim}：{pipeline.RUBRIC_DESCRIPTIONS.get(dim, '')}")
    print("\nDefault (Whisper back-translation + LLM) evaluation scores conservatively based on 'transcribed text + duration + speech rate + CER';")
    print("--gemini lets the multimodal model listen to audio directly, covering dimensions like 'emotional expression / timbre consistency' in the book.")


def main():
    global OUT_DIR
    ap = argparse.ArgumentParser(
        description="Fully automated TTS quality evaluation pipeline (Experiment 6-5): multi-provider synthesis + multimodal LLM Rubric evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n"
               "  python demo.py                          Default 4 OpenAI configs × 4 test sentences\n"
               "  python demo.py --providers openai,minimax   Cross-provider horizontal comparison\n"
               "  python demo.py --text '今天天气不错' --gemini   Custom text + Gemini multimodal evaluation\n"
               "  python demo.py --list-providers         View providers and config status offline\n"
               "  python demo.py --dump-rubric            View Rubric dimension definitions offline",
    )
    ap.add_argument("--text", metavar="text",
                    help="Replace the test corpus with a custom text segment (evaluate only this sentence)")
    ap.add_argument("--providers", metavar="list",
                    help="Comma-separated providers (openai,elevenlabs,fishaudio,minimax,doubao),"
                         "each takes a representative config for horizontal comparison; default only OpenAI multi-config")
    ap.add_argument("--judge-model", metavar="model", dest="judge_model",
                    help=f"Override LLM evaluation model (default {config.JUDGE_MODEL}); not effective with --gemini")
    ap.add_argument("--output", metavar="dir",
                    help=f"Output directory (audio + results.json), default {OUT_DIR}")
    ap.add_argument("--extra", action="store_true", help="Additionally add gpt-4o-mini-tts config")
    ap.add_argument("--gemini", action="store_true", help="Use Gemini multimodal to listen to audio directly for evaluation (requires GEMINI_API_KEY)")
    ap.add_argument("--quick", action="store_true", help="Quick smoke test using only the first 2 test sentences")
    ap.add_argument("--fresh", action="store_true", help="Ignore existing audio, re-synthesize all")
    ap.add_argument("--list-providers", action="store_true", dest="list_providers",
                    help="Print all TTS providers and config status offline then exit (no key required)")
    ap.add_argument("--dump-rubric", action="store_true", dest="dump_rubric",
                    help="Print Rubric dimension definitions offline then exit (no key required)")
    args = ap.parse_args()

    load_env()

    #  Offline mode: no internet, no API key required, exits after printing.
    if args.list_providers:
        print_providers()
        return
    if args.dump_rubric:
        print_rubric()
        return

    if args.output:
        OUT_DIR = os.path.abspath(args.output)
    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.environ.get("OPENAI_API_KEY", "").strip():
        print("Error: missing OPENAI_API_KEY (required for back-translation/default review). Please export or write to .env and retry.",
              file=sys.stderr)
        sys.exit(1)

    #  Select configurations to compare: --providers takes precedence (cross-provider), otherwise default OpenAI multi-config.
    if args.providers:
        configs = []
        for key in [p.strip() for p in args.providers.split(",") if p.strip()]:
            if key not in config.PROVIDER_CONFIGS:
                print(f"Error: unknown provider {key!r}. Available: {', '.join(config.PROVIDER_CONFIGS)}",
                      file=sys.stderr)
                sys.exit(1)
            configs.append(config.PROVIDER_CONFIGS[key])
    else:
        configs = list(config.TTS_CONFIGS)
        if args.extra:
            configs += config.EXTRA_CONFIGS

    if args.text:
        corpus = [config.Sample(id="custom", text=args.text,
                                challenge="Custom text", emotion="Neutral")]
    else:
        corpus = config.CORPUS[:2] if args.quick else config.CORPUS

    judge_model = args.judge_model or config.JUDGE_MODEL
    mode = ("Gemini multimodal audio review" if args.gemini
            else f"Whisper back-translation + LLM Rubric ({judge_model}）")
    providers_used = sorted({getattr(c, "provider", "openai") for c in configs})
    print("=" * 72)
    print(f"Experiment 6-5: Fully automated TTS quality evaluation pipeline")
    print(f"Review mode: {mode}")
    print(f"Participating providers: {', '.join(providers_used)}")
    print(f"Config count: {len(configs)}   Corpus count: {len(corpus)}   "
          f"Total {len(configs)*len(corpus)} items to evaluate")
    print("=" * 72)

    records = []
    t0 = time.time()
    for cfg in configs:
        print(f"\n### Configuration {cfg.name}  (provider={getattr(cfg,'provider','openai')}, "
              f"model={cfg.model}, voice={cfg.voice}, speed={cfg.speed})")
        for sample in corpus:
            rec = evaluate_one(cfg, sample, args.gemini, args.fresh,
                               judge_model=None if args.gemini else args.judge_model)
            print_detail(rec, sample.text)
            records.append(rec)

    rows = summarize(records)
    print("\n" + "=" * 72)
    print("Configuration comparison summary (sorted by overall score descending)")
    print("=" * 72)
    print_table(rows)

    ok = sum(1 for r in records if r["ok"])
    print(f"\nCompleted: {ok}/{len(records)} items succeeded, elapsed {time.time()-t0:.1f}s。")

    #  Persisted structured results for secondary analysis
    out_json = os.path.join(OUT_DIR, "results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"records": records, "summary": rows}, f,
                  ensure_ascii=False, indent=2)
    print(f"Detailed results written to {out_json}")


if __name__ == "__main__":
    main()
