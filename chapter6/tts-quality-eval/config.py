"""Experiment 6-5: Fully Automated TTS Quality Evaluation Pipeline — Configuration and Test Corpus.

This module centrally manages:
  - The OpenAI model names and billing rates used (for cost estimation only);
  - Multiple TTS "configurations" (combinations of model / voice / speed, as objects to be compared);
  - A set of challenging reference texts (numbers / polyphonic characters / long sentences / proper nouns + emotion).
"""

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Model name (all OpenAI, read OPENAI_API_KEY).
# ---------------------------------------------------------------------------
WHISPER_MODEL = "whisper-1"        # Speech transcription (back-translation) for computing WER/word accuracy (must use OpenAI direct connection)
JUDGE_MODEL = "gpt-5.6-luna"       # LLM Rubric evaluation model (current budget flagship; chat calls can fall back to OpenRouter)

# Optional Gemini audio review (scheme in the book). Default uses the current cheap flagship gemini-3.5-flash (verified support
# Audio input, can directly 'hear' synthesized speech). Model names may expire over time, runtime uses REST /models
#  Probe correction. Only used when --gemini is enabled.
GEMINI_MODEL_DEFAULT = "gemini-3.5-flash"

# Billing unit price (USD), only used for printing rough cost, does not affect scoring. The value may change with official adjustments.
PRICE = {
    "tts-1": 15.0 / 1_000_000,          # $ / character
    "tts-1-hd": 30.0 / 1_000_000,       # $ / character
    "gpt-4o-mini-tts": 12.0 / 1_000_000,
    "whisper-1": 0.006 / 60,            # $ / sec
}


@dataclass
class TTSConfig:
    """A TTS configuration to be evaluated. The name must be unique within the entire table.

    provider specifies which service to use for synthesis (openai / elevenlabs / fishaudio / minimax /
    doubao). The semantics of model / voice / speed are interpreted by each provider: for example, elevenlabs'
    voice is a voice_id, fishaudio's voice is a reference_id (can be left empty to use the default timbre).
    """

    name: str
    model: str
    voice: str
    speed: float = 1.0
    provider: str = "openai"

    def supports_speed(self) -> bool:
        #  Only some providers/models support the speed parameter; this field is ignored when not supported.
        if self.provider == "openai":
            return self.model in ("tts-1", "tts-1-hd")
        return self.provider in ("minimax", "doubao")


# ---------------------------------------------------------------------------
# Multi-provider registry (corresponding to the book's "Accessing Mainstream Services: OpenAI, ElevenLabs, Fish Audio,
# Minimax, Doubao). Each provider declares required environment variables and a representative configuration for cross-service
#  Horizontal comparison. Except for OpenAI, all are implemented according to each provider's public REST interface. When a key is missing, the row for that provider will be
#  Mark as failed without affecting the entire table (see demo.py).
# ---------------------------------------------------------------------------
# Environment variable aliases: the same credential may have multiple historical/commonly used names; if any one of them is set, it is considered configured.
ENV_ALIASES = {
    "FISH_API_KEY": ("FISH_API_KEY", "FISHAUDIO_API_KEY"),
}


def env_get(name: str) -> str:
    """Read environment variables, supporting aliases registered in ENV_ALIASES, and return the first non-empty value (stripped)."""
    import os
    for n in ENV_ALIASES.get(name, (name,)):
        val = os.environ.get(n, "").strip()
        if val:
            return val
    return ""


@dataclass
class ProviderInfo:
    key: str                #  Internal identifier (for --providers)  
    label: str              # Display Name
    env: tuple              #  The environment variable name required for the provider synthesis
    note: str               #  A sentence explaining the semantics of the voice field, etc.

    def configured(self) -> bool:
        return all(env_get(e) for e in self.env)


PROVIDERS = {
    "openai": ProviderInfo(
        "openai", "OpenAI", ("OPENAI_API_KEY",),
        "voice=alloy/nova/…, model=tts-1/tts-1-hd/gpt-4o-mini-tts; the only end-to-end verified provider in this repository.",
    ),
    "elevenlabs": ProviderInfo(
        "elevenlabs", "ElevenLabs", ("ELEVENLABS_API_KEY",),
        "voice=voice_id, model defaults to eleven_multilingual_v2 (multilingual/Chinese).",
    ),
    "fishaudio": ProviderInfo(
        "fishaudio", "Fish Audio", ("FISH_API_KEY",),
        "voice=reference_id (leave empty to use default voice), use /v1/tts; key can also use alias FISHAUDIO_API_KEY.",
    ),
    "minimax": ProviderInfo(
        "minimax", "Minimax", ("MINIMAX_API_KEY", "MINIMAX_GROUP_ID"),
        "voice=voice_id, model defaults to speech-01-turbo; additional GroupId required.",
    ),
    "doubao": ProviderInfo(
        "doubao", "Doubao (Volcano Engine)", ("DOUBAO_APP_ID", "DOUBAO_ACCESS_TOKEN"),
        "voice=voice_type, go to openspeech.bytedance.com; the authentication header is 'Bearer;{token}'.",
    ),
}

# Representative configuration of each provider (when --providers is selected, each provider takes this one for comparison).
# For non-OpenAI voice/model, common defaults from various providers are used; you can adjust here based on the available voices for your account.
PROVIDER_CONFIGS = {
    "openai": TTSConfig("openai-alloy", provider="openai", model="tts-1", voice="alloy"),
    "elevenlabs": TTSConfig("elevenlabs-multi", provider="elevenlabs",
                            model="eleven_multilingual_v2", voice="21m00Tcm4TlvDq8ikWAM"),
    "fishaudio": TTSConfig("fishaudio-default", provider="fishaudio",
                          model="speech-1.5", voice=""),
    "minimax": TTSConfig("minimax-turbo", provider="minimax",
                        model="speech-01-turbo", voice="male-qn-qingse"),
    "doubao": TTSConfig("doubao-tts", provider="doubao",
                       model="volcano_tts", voice="zh_female_qingxin"),
}


# Default comparison configuration set: covers three dimensions—model (tts-1 vs tts-1-hd), voice, and speed,
# facilitating observation of differences in accuracy/naturalness across configurations. Defaults to using OpenAI entirely to ensure zero extra configuration works out of the box.
TTS_CONFIGS = [
    TTSConfig("tts1-alloy-1.0", model="tts-1", voice="alloy", speed=1.0),
    TTSConfig("tts1hd-alloy-1.0", model="tts-1-hd", voice="alloy", speed=1.0),
    TTSConfig("tts1-nova-1.0", model="tts-1", voice="nova", speed=1.0),
    TTSConfig("tts1-alloy-1.5", model="tts-1", voice="alloy", speed=1.5),
]

# Optionally include (enabled via --extra): gpt-4o-mini-tts. Not included by default to guarantee a baseline run.
EXTRA_CONFIGS = [
    TTSConfig("4omini-nova-1.0", model="gpt-4o-mini-tts", voice="nova", speed=1.0),
]


@dataclass
class Sample:
    """ A reference text + expected emotion label (for Rubric emotion dimension reference)."""

    id: str
    text: str
    challenge: str      # The main challenge points tested by this sample
    emotion: str = "Neutral"


# Diverse test corpus: numbers/dates, polyphonic characters, long sentences, proper nouns + emotion.
CORPUS = [
    Sample(
        id="num",
        text="In the third quarter of 2026, revenue grew by 37.5%, an increase of 12 percentage points year-over-year.",
        challenge="Numbers/Percentages/Dates",
        emotion="Neutral",
    ),
    Sample(
        id="polyphone",
        text="The bank president is re-prioritizing this matter; in the long run, all debts must still be repaid.",
        challenge="Polyphonic characters (行/长/重/还)",
        emotion="Neutral",
    ),
    Sample(
        id="long",
        text="According to reports, with the rapid development of AI technology, more and more enterprises are starting to apply large language models"
             "to scenarios such as customer service, content creation, and data analysis, thereby significantly improving operational efficiency.",
        challenge="Long sentence/News style",
        emotion="Neutral",
    ),
    Sample(
        id="emotion",
        text="Awesome! The new model just released by OpenAI has performed amazingly on the GAIA benchmark!",
        challenge="Proper noun + Exclamation emotion",
        emotion="Excited",
    ),
]
