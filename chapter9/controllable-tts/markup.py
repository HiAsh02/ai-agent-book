"""
Control Markup Parser
=====================

Parses text with control markup into a sequence of "segments", each of which is either a speech segment to be synthesized with a reference voice, or a silence segment. This step corresponds to "the execution layer parses markup and maps to corresponding reference voices" in the book.

Two types of markup are supported:

1) State markers (persist until changed by the next same-type marker)
   [EMO:neutral|happy|frustrated|thinking]           or  [emotion=neutral|happy|frustrated|thinking]
   [SPEED:normal|fast|slow] / [SPEED:0.8x]           or  [speed=normal|fast|slow]
   [STYLE:formal|casual]                             or  [style=formal|casual]

2) Inline markers (one-time events, insert pauses / fillers / non-verbal sounds, or temporarily change state)
   [THINKING]   Thinking pause + hesitant tone (= emotion thinking / slow / formal, with pause inserted)
   [SEARCHING]  Searching pause (same, slightly shorter pause)
   [PAUSE] / <pause> / [pause]     Insert pause
   [BREATH] / <breath>             Breath pause
   [SIGH]  / <sigh>                Sigh (approximated with sigh onomatopoeia)
   [LAUGH:small] / [LAUGH] / <laugh>   Light laugh (approximated with laugh onomatopoeia)
   <emphasis>...</emphasis> / [emphasis]...[/emphasis]   Emphasize the enclosed text

Note: OpenAI TTS cannot "natively generate" non-verbal sounds like laughter/sighs like Fish Audio can; here we approximate using "onomatopoeia + matching emotion" (see README provider adaptation notes).
"""

import re

# Chinese values -> alias mapping for English dimension values
_EMO_ALIAS = {
    "neutral": "neutral", "happy": "happy", "happy": "happy", "excited": "happy",
    "frustrated": "frustrated", "helpless": "frustrated", "thinking": "thinking",
}
_SPEED_ALIAS = {"normal": "normal", "fast": "fast", "fast": "fast", "slow": "slow", "slow": "slow"}
_STYLE_ALIAS = {"formal": "formal", "casual": "casual", "casual": "casual"}

# Pause duration (ms) for each inline event
PAUSE_MS = 500
BREATH_MS = 400
THINKING_MS = 500
SEARCHING_MS = 400
SIGH_TAIL_MS = 300


def _norm(value: str, alias: dict) -> str:
    v = value.strip()
    return alias.get(v, v.lower())


class Segment(dict):
    """A segment: type='speech'(text, emotion, speed, style, emphasis) or type='silence'(ms)."""


def parse(text: str, trace: list | None = None):
    """
    Parse text with control markup and return a list of segments.
    If trace (list) is provided, the parsing process of "marker -> action" will be recorded line by line for printing.
    """
    def log(msg):
        if trace is not None:
            trace.append(msg)

    # Current state (state markers will change it persistently)
    state = {"emotion": "neutral", "speed": "normal", "style": "formal", "emphasis": False}
    segments: list[Segment] = []
    buf = []  # Accumulated plain text under current state

    def flush():
        """Flush the buffered plain text as a speech segment."""
        s = "".join(buf).strip()
        buf.clear()
        if s:
            segments.append(Segment(type="speech", text=s, **state))

    def add_silence(ms, why):
        flush()
        segments.append(Segment(type="silence", ms=ms))
        log(f"  {why:22s} -> Insert silence {ms}ms")

    def add_speech_token(token, emotion, speed, style, why):
        """Insert an independent short speech segment with specified emotion (for onomatopoeia like laughter/sighs)."""
        flush()
        segments.append(Segment(type="speech", text=token, emotion=emotion,
                                speed=speed, style=style, emphasis=False))
        log(f"  {why:22s} -> Onomatopoeia speech '{token}' (emotion={emotion}, speed={speed})")

    def set_state(**kw):
        flush()  # Before state change, flush the old state's text
        for k, v in kw.items():
            state[k] = v

    # Use a single regex to extract all [..] and <..> markers, the rest is plain text
    parts = re.split(r"(\[[^\]]*\]|<[^>]+>)", text)
    for part in parts:
        if not part:
            continue
        if not re.fullmatch(r"\[[^\]]*\]|<[^>]+>", part):
            buf.append(part)  # plain text
            continue

        m = part  # mark original text
        inner = m[1:-1].strip()

        # --- Status markers: EMO / SPEED / STYLE (English colon style or Chinese equals sign style) ---
        km = re.match(r"(?i)^(EMO|SPEED|STYLE)\s*:\s*(.+)$", inner)
        cm = re.match(r"^(emotion|speed|style)\s*=\s*(.+)$", inner)
        if km:
            key, val = km.group(1).upper(), km.group(2)
        elif cm:
            key = {"emotion": "EMO", "speed": "SPEED", "style": "STYLE"}[cm.group(1)]
            val = cm.group(2)
        else:
            key = val = None

        if key == "EMO":
            e = _norm(val, _EMO_ALIAS)
            set_state(emotion=e)
            log(f"  {m:22s} -> emotion = {e}")
            continue
        if key == "SPEED":
            raw = val.strip()
            v = raw.lower().replace("x", "")  # compatible with 0.8x
            # first recognize English values (normal/fast/slow), then Chinese aliases (正常/快/慢)
            if v in ("normal", "fast", "slow"):
                s = v
            elif raw in _SPEED_ALIAS:
                s = _SPEED_ALIAS[raw]
            else:
                # numeric type (e.g., 0.8) maps to fast/slow/normal nearby, only for display
                try:
                    f = float(v)
                    s = "fast" if f > 1.05 else ("slow" if f < 0.95 else "normal")
                except ValueError:
                    s = "normal"
            set_state(speed=s)
            log(f"  {m:22s} -> speed = {s}")
            continue
        if key == "STYLE":
            st = _norm(val, _STYLE_ALIAS)
            set_state(style=st)
            log(f"  {m:22s} -> style = {st}")
            continue

        # --- Emphasis wrapping ---
        low = inner.lower()
        if low in ("emphasis", "emphasis"):
            set_state(emphasis=True)
            log(f"  {m:22s} -> enable emphasis")
            continue
        if low in ("/emphasis", "/emphasis"):
            set_state(emphasis=False)
            log(f"  {m:22s} -> disable emphasis")
            continue

        # --- Inline event markers ---
        tag = low.split(":")[0]  # laugh:small -> laugh
        if tag == "thinking":
            set_state(emotion="thinking", speed="slow", style="formal")
            log(f"  {m:22s} -> switch to thinking/slow/formal reference voice")
            add_silence(THINKING_MS, "[THINKING] pause")
            continue
        if tag == "searching":
            set_state(emotion="thinking", speed="slow", style="formal")
            log(f"  {m:22s} -> switch to thinking/slow/formal reference voice")
            add_silence(SEARCHING_MS, "[SEARCHING] pause")
            continue
        if tag in ("pause", "pause"):
            add_silence(PAUSE_MS, m)
            continue
        if tag in ("breath", "breath"):
            add_silence(BREATH_MS, m)
            continue
        if tag == "sigh":
            add_speech_token("ah——", "frustrated", "slow", "formal", m)
            segments.append(Segment(type="silence", ms=SIGH_TAIL_MS))
            continue
        if tag == "laugh":
            add_speech_token("haha,", "happy", "fast", "casual", m)
            continue

        # unknown marker: ignore but record
        log(f"  {m:22s} -> [unknown marker, ignored]")

    flush()
    return segments


# ---------------------------------------------------------------------------
# static mapping table from control markers to actions (offline queryable, for demo.py --dump-mapping)
# This is the single source of truth for the mapping from control markers in the book to reference voices / non-verbal sounds.
# ---------------------------------------------------------------------------

# (Category, Tag Syntax, Chinese Syntax, Mapped Action)
MARKER_REFERENCE = [
    ("State", "[EMO:neutral|happy|frustrated|thinking]", "[Emotion=Neutral|Happy|Frustrated|Thinking]",
     "Switch emotion dimension, select reference voice"),
    ("State", "[SPEED:normal|fast|slow] / [SPEED:0.8x]", "[Speed=Normal|Fast|Slow]",
     "Switch speed dimension (numeric values map to fast/slow/normal)"),
    ("State", "[STYLE:formal|casual]", "[Style=Formal|Casual]", "Switch tone dimension"),
    ("Inline", "[THINKING]", "—", "Switch to 'Thinking/Slow/Formal' reference voice + insert 500ms pause"),
    ("Inline", "[SEARCHING]", "—", "Switch to 'Thinking/Slow/Formal' reference voice + insert 400ms pause"),
    ("Inline", "[PAUSE] / <pause>", "[Pause]", "Insert 500ms silence"),
    ("Inline", "[BREATH] / <breath>", "[Breath]", "Insert 400ms breath pause"),
    ("Inline", "[SIGH] / <sigh>", "—", "Sigh onomatopoeia 'Ai——' (frustrated tone) + 300ms pause"),
    ("Inline", "[LAUGH:small] / [LAUGH] / <laugh>", "—", "Light laugh onomatopoeia 'Haha,' (happy tone)"),
    ("Inline", "<emphasis>…</emphasis>", "[Emphasis]…[/Emphasis]", "Append 'emphasis' prompt to wrapped text"),
]


def format_marker_reference() -> str:
    """Render MARKER_REFERENCE as a printable aligned table string."""
    lines = [f"{'Category':<4} {'Tag Syntax':<40} {'Chinese Syntax':<24} Action", "-" * 100]
    for cat, mark, zh, action in MARKER_REFERENCE:
        lines.append(f"{cat:<4} {mark:<40} {zh:<24} {action}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("Control Tag -> Action Mapping Table: \n")
    print(format_marker_reference())
