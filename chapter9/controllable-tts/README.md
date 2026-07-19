# Experiment 9-5: Control-Marker-Driven Controllable TTS

A runnable companion project for Experiment 9-5 of "Deep Understanding of AI Agents".

Core idea: The main LLM's output is not just text, but also includes **control markers** (emotion/speech rate/style/pause/laughter, etc.); the execution layer parses these markers, maps them to corresponding timbre/style profiles in a **reference voice library**, and then synthesizes speech. This way, decisions about "where to pause and what tone to use" are delegated to the LLM. The same text, with different control markers, can synthesize speech with different styles, emotions, and rhythms.

## Provider Adaptation (Important)

Experiment 9-5 in the book uses **Fish Audio S1** for voice cloning: uses 3-10 seconds of reference audio for zero-shot cloning of the same timbre, builds a reference voice library covering emotion × speech rate × style, selects reference voices via control markers, and Fish Audio ensures **consistent timbre** across different reference voices with only changes in prosody and emotion.

This environment lacks a usable Fish Audio key, so **OpenAI TTS** is used instead to demonstrate the **exact same concept**:

| Book (Fish Audio) | This Project (OpenAI TTS) |
| --- | --- |
| Voice cloning ensures consistent timbre | Entire library uses a fixed `voice` (alloy), timbre unchanged |
| Prosody/emotion of each reference voice | Each profile corresponds to a set of `instructions` style prompts |
| Control markers select reference voice | Control markers parsed -> select `(emotion, speed, style)` profile |

- Preferred model **`gpt-4o-mini-tts`**: Supports the `instructions` parameter, allowing precise control of emotion/speech rate/tone with a Chinese prompt, closest to the semantics of "control marker → stylized speech".
- If the preferred model is unavailable, the code **automatically falls back to `tts-1`**: Does not support instructions, instead uses multiple voices + `speed` parameter + text-level pauses as an approximation.

**Must use a direct OpenAI Key**: This experiment only uses the TTS speech synthesis endpoint (`gpt-4o-mini-tts` / `tts-1`). These audio endpoints are only available through direct OpenAI connection—OpenRouter only handles chat completions and has no audio synthesis endpoint, so it cannot fall back to `OPENROUTER_API_KEY`. Offline viewing of the voice library/marker mapping (`--list-voices` / `--dump-mapping`) does not require any key.

> Limitation: OpenAI TTS cannot **natively generate** non-verbal sounds like laughter or sighs like Fish Audio can. This project approximates `<laugh>` / `[SIGH]` with emotion-matching onomatopoeia (e.g., "Haha," "Ahh—"), while `[PAUSE]`/`[THINKING]` and other pauses use ffmpeg to generate **real silence** that can be verified for duration by ffprobe.

## Control Marker → TTS Parameter Mapping

### State Markers (persist until changed by a similar marker)

| Marker | Chinese Form | Effect |
| --- | --- | --- |
| `[EMO:neutral\|happy\|frustrated\|thinking]` | `[EMO=neutral\|happy\|frustrated\|thinking]` | Switch emotion |
| `[SPEED:normal\|fast\|slow]` / `[SPEED:0.8x]` | `[SPEED=normal\|fast\|slow]` | Switch speech rate |
| `[STYLE:formal\|casual]` | `[STYLE=formal\|casual]` | Switch tone |
The three dimensions combine to form a profile in the reference voice library (e.g., `happy_fast_formal`), which is then assembled into an `instructions` prompt for `gpt-4o-mini-tts`.

### Inline Markers (one-time events)

| Marker | Effect |
| --- | --- |
| `[THINKING]` | Switch to "thinking/slow/formal" reference voice + insert 0.5s pause |
| `[SEARCHING]` | Same as above, 0.4s pause (searching hesitation) |
| `[PAUSE]` / `<pause>` / `[停顿]` | Insert 0.5s silence || `[BREATH]` / `<breath>` | Insert 0.4s breathing pause |
| `[SIGH]` / `<sigh>` | Sigh onomatopoeia "Ahh—" + 0.3s pause |
| `[LAUGH:small]` / `<laugh>` | Light laugh onomatopoeia "Haha," (cheerful tone) |
| `<emphasis>…</emphasis>` / `[强调]…[/强调]` | Append "emphasize" prompt for the wrapped text |
### Reference Voice Library

`voice_library.py` generates **24 profiles** from the Cartesian product of emotion(4) × speech rate(3) × style(2), all with a fixed `voice=alloy` (consistent timbre), differing only in `instructions`. Can be viewed by running it standalone:

```bash
python voice_library.py
```

## Installation and Execution

```bash
pip install -r requirements.txt          # Requires ffmpeg/ffprobe installed on the system
cp env.example .env                       # Fill in a valid OPENAI_API_KEY
python demo.py                            # Generates output/*.mp3
```

`demo.py` does two things:

1. **Comparison of three configurations** (as required by the book), using the same text with markers:
   - `A_no_markers.mp3` No control markers (fluent but mechanical)
   - `B_single_voice.mp3` Single reference voice (natural but emotionally monotone)
   - `C_voice_library.mp3` Multiple reference voice library (switches emotion/speech rate/pause based on markers)
2. **Same text / different control markers** → multiple different style audio files: `variant_*.mp3`.

During execution, it prints the "control marker → parameter" parsing process for each audio file, along with ffprobe duration information.

Common parameters (`python demo.py --help`):

| Parameter | Effect |
| --- | --- |
| `--quick` | Only run the three-configuration comparison (A/B/C), skip the 5 style variants, reducing TTS calls and time |
| `--text text` | Only synthesize this custom text (can embed control markers, e.g., `[emotion=happy][THINKING]…`) || `--emotion / --speed / --style` | Specify emotion/speech rate/tone for `--text` (equivalent to adding corresponding state markers before the text) |
| `-o / --output path` | Output mp3 path for `--text` mode (default `output/custom.mp3`) |
| `--list-voices` | **Offline** (no API key needed): Print the complete reference voice library (24 profiles and their instructions) |
| `--dump-mapping` | **Offline** (no API key needed): Print the control marker → action mapping table, and demonstrate the parsing process on example text |

## Example Expected Output (Real Excerpt)

```
Preferred model: gpt-4o-mini-tts (automatically falls back to tts-1 if unavailable)

Comparison experiment: Same text with control markers, three configurations
[EMO:happy][SPEED:fast]Great! Your order has been confirmed.[THINKING]Hmm, let me check the delivery time...[EMO:neutral][SPEED:normal]It is expected to arrive tomorrow afternoon.
[C] Multiple reference voice library (parse control markers -> switch reference voice per segment + pauses)
    -- Control marker parsing process --
  [EMO:happy]            -> emotion = happy
  [SPEED:fast]           -> speech rate = fast
  [THINKING]             -> Switch to thinking/slow/formal reference voice
  [THINKING] pause          -> Insert silence 500ms
    -- Synthesis segments --
    · [happy_fast_formal         ] gpt-4o-mini-tts  voice=alloy text='Great! Your order has been confirmed.'    · [Silence 500ms]
    · [thinking_slow_formal      ] gpt-4o-mini-tts  voice=alloy text='Hmm, let me check the delivery time...'
    · [neutral_normal_formal     ] gpt-4o-mini-tts  voice=alloy text='It is expected to arrive tomorrow afternoon.'  => output/C_voice_library.mp3  |  format_name=mp3  duration=11.324000  ...
```

Comparing the ffprobe durations of the three configurations reveals the difference: C (multiple reference voice library) is longer (approximately 11.3s) than A/B (approximately 8.5s) due to the inserted real silence pauses, and each segment uses a different `(emotion, speech rate, style)` profile. (Each run will actually call OpenAI TTS, so duration/byte count will have slight fluctuations.)

## File Descriptions

| File | Description |
| --- | --- |
| `voice_library.py` | Reference voice library + control dimension → instructions mapping |
| `markup.py` | Control marker parser: text with markers → list of segments (speech/silence) |
| `tts.py` | OpenAI TTS synthesis + ffmpeg silence generation/concatenation |
| `demo.py` | Demo entry point, three-configuration comparison + style variants |
