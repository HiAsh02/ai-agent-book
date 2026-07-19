# Experiment 9-3: Streaming Speech Perception

Companion to Chapter 9 of "Understanding AI Agents" – Experiment 9-3: Using Qwen2-Audio to Simulate Streaming Speech Perception.

## Objective

Demonstrate the core trade-off of **streaming speech perception**: feed continuous audio to ASR in **incrementally growing chunks**, producing a "current partial recognition result" after each small segment. This achieves extremely low **first-packet latency** for obtaining text; the cost is that early chunks, **lacking the latter half of the sentence context** and with speech cut off mid-stream, may produce **incomplete or erroneous** recognition, which gradually **converges** to the correct text as more audio accumulates. As a baseline, "wait for the complete audio and then recognize once" is the most accurate, but requires waiting for the entire sentence plus inference, resulting in the **highest latency for the first character**.

The phenomenon from the original experiment in the book: in a sentence with a pause, "大概两点左右" (around two o'clock) was misrecognized as "大概零点左右" (around midnight) in an overly early chunk. This demo replicates this "cost of premature decision" with a similar phenomenon.
## Model Adaptation Notes (Important)

- The original experiment in the book used **Qwen2-Audio** (a native audio model capable of outputting acoustic event tokens like `<|noise|>`).
  However, it currently **has no directly callable key/endpoint**, so this demo uses an **available ASR alternative**:
  **OpenAI Whisper (`whisper-1`)**, reading the `OPENAI_API_KEY`.
- Choosing Whisper is appropriate: like Qwen2-Audio, it is a **non-streaming model that takes the entire segment as input** – the encoder needs the full audio segment to start working and is **non-incremental** (each longer prefix requires re-encoding from scratch).
  Therefore, "slicing by increasing prefixes and recognizing each slice" perfectly reproduces the mechanism and cost of "simulated streaming" described in the book.
- The test audio is synthesized on the fly using **OpenAI TTS (`tts-1`)**. The sentence contains time information "两点半" (two thirty). When the first half is truncated, it is prone to incomplete/erroneous recognition.- **Must use a direct OpenAI Key**: This experiment only uses audio endpoints (ASR `whisper-1` / TTS `tts-1`). These endpoints are only available via direct OpenAI connection – OpenRouter only handles chat completions and has no audio endpoints, so it cannot fall back to `OPENROUTER_API_KEY`. If you only want to verify the chunking/timing logic, use `python demo.py --offline`, which requires no Key.

Compared to true streaming models (e.g., Qwen3-Omni using chunked/causal encoders), the latency numbers in this demo only reflect the overhead of "chunk granularity + re-encoding each chunk from scratch" and do not equal the first-packet latency of true streaming; this is also explained in the book.

## Streaming Chunking Mechanism

1. Synthesize the entire Chinese test audio using TTS (approx. 7–8 seconds), saved as `audio/sentence.wav`.
2. Use `ffmpeg` to slice out "all audio received so far" at increasing lengths: `t = 0.5s, 1.0s, 1.5s ...`,
   simulating the continuous arrival of an audio stream.
3. For each prefix chunk, call Whisper to obtain the "current partial recognition result", recording the **single-chunk recognition latency** and **cumulative arrival latency**.
4. Baseline: At the end, recognize the **entire** audio segment once, recording its result and latency.
5. Print a per-chunk recognition table + full-segment baseline, quantifying the latency/accuracy trade-off between "first available recognition" and "full-segment recognition".

## Running

```bash
cd chapter9/streaming-speech
pip install -r requirements.txt          # Also requires ffmpeg on the machine: brew install ffmpeg
cp env.example .env                       # Fill in OPENAI_API_KEY (or directly export)
python demo.py                             # Default: TTS synthesis + 0.5s granularity real Whisper streaming recognition
python demo.py --quick                     # Increase chunk granularity to 1.5s, reducing Whisper calls to ~1/3
python demo.py --sentence "..." --chunk-step 0.5   # Custom test sentence and chunk granularity
python demo.py --audio my.wav              # Use an existing audio file as input, skip TTS synthesis
python demo.py --compare-chunks            # Cross-granularity (0.5/1.0/2.0s) latency comparison table
python demo.py --offline                   # Offline self-test: no network, no ffmpeg, no Key, uses a synthetic recognizer
python demo.py --offline --compare-chunks  # Offline synthetic cross-granularity latency comparison table
python demo.py --output result.json        # Save results (per-chunk table/comparison table) as JSON
python demo.py --help                      # View all parameters
```

Common parameters (`python demo.py --help`):

- `--sentence`: Test sentence (default is a sentence with time information similar to the one in the book).
- `--chunk-step`: Chunk granularity (seconds), default 0.5. Smaller values mean more chunks and slower processing.
- `--quick`: Increase granularity to 1.5s for a quick demo (Whisper calls reduced to ~1/3).
- `--audio PATH`: Use an existing audio file as input, skip TTS synthesis (ignored in offline mode).
- `--compare-chunks [S1,S2,...]`: Run once for each specified chunk granularity, output a cross-granularity latency comparison table; if no value is given, defaults to `0.5,1.0,2.0` (seconds).
- `--offline`: **Offline self-test**, no network, no ffmpeg, no Key needed. Uses a **synthetic recognizer** (SYNTHETIC) to drive the same chunking/timing logic – text is revealed proportionally to the prefix, latency values are synthetic, **only validates the process, does not represent any real model performance**.
- `--duration SEC`: Total duration of the segment in offline mode (default is estimated based on sentence length).
- `--tts-model` / `--voice` / `--asr-model` / `--language`: Override TTS/ASR models and language (defaults are `tts-1` / `alloy` / `whisper-1` / `zh`).
- `--output PATH`: Save results as JSON.

## Real Run Output (Excerpt, for Reference)

A real run (sentence: "Please help me reschedule tomorrow afternoon's meeting to 2:30, the location is still Conference Room 3, and don't forget to notify everyone.", total duration 7.75s) per-chunk recognition:
```
Chunk#01  Audio Prefix  0.5s | Recognition: Could you please                         ← Premature truncation: misrecognition + incomplete
Chunk#03  Audio Prefix  1.5s | Recognition: Could you please reschedule tomorrow afternoon's
Chunk#05  Audio Prefix  2.5s | Recognition: ...to two o'clock                       ← Time only half heard
Chunk#06  Audio Prefix  3.0s | Recognition: ...to two thirty                     ← Converges after context is supplemented
Chunk#10  Audio Prefix  5.0s | Recognition: ...the location is still in Sichuan                 ← Truncation misrecognition (should be "Conference Room 3")
Chunk#12  Audio Prefix  6.0s | Recognition: ...the location is still in Conference Room 3           ← Converges with more audio
Chunk#14  Audio Prefix  7.0s | Recognition: ...don't forget to notify me                   ← Another premature misjudgment (should be "notify everyone")
Chunk#16  Audio Prefix  7.8s | Recognition: ...don't forget to notify everyone (Complete and correct)
Full Segment Recognition (wait for complete audio): Could you please reschedule tomorrow afternoon's meeting to 2:30 PM? The location is still Conference Room 3. Don't forget to notify everyone.  Wait time: 7.75s (recording) + 2.25s (inference)
First available streaming recognition: Only ~0.5s of audio needed to produce a partial result, obtaining the first version 7.2s earlier than the full segment.
```

It can be seen: streaming chunking advances the latency of the "first partial result" from "after recording the full sentence (7.75s)" to "after receiving 0.5s of audio", but the cost is **premature decision misrecognitions** in early chunks like "你帮我→你们" (you help me → you all), "三号会议室→四川" (Conference Room 3 → Sichuan), "通知大家→通知我" (notify everyone → notify me), which gradually converge as audio accumulates. Full segment recognition is the most accurate but has the highest latency. This is the **latency vs. accuracy trade-off** of streaming speech perception.
> Note: Each run makes real calls to TTS + Whisper, so the specific recognized text and latency numbers will fluctuate slightly;
> the table above is the result of one particular real run. The positions of misrecognitions in early chunks may vary between runs, but the pattern of "early inaccuracy, convergence with more audio" is stably reproduced.

## File Description

- `demo.py`: Main program (synthesize audio → incremental chunk streaming recognition → full segment baseline).
- `requirements.txt`: Python dependencies (also requires ffmpeg/ffprobe on the machine).
- `env.example`: Environment variable example, copy to `.env` and fill in `OPENAI_API_KEY`.
- `audio/`: Audio generated at runtime (gitignored).
