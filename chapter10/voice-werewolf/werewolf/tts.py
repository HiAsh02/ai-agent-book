# -*- coding: utf-8 -*-
"""Optional Text-to-Speech (TTS) – synthesizes players' public messages into speech.

Voice is an **optional enhancement** for this experiment, not required to run: the default text mode is sufficient to complete a full game and
verify information isolation. It is only enabled with --voice, using OpenAI tts-1 to synthesize each public message into mp3,
saved to the audio/ directory; on macOS, afplay can be used to play them on the fly (--play).
"""

import os
import subprocess

from .agent import get_client


#Assign different voices to different players for easy distinction
_VOICES = ["alloy", "echo", "fable", "onyx", "nova", "shimmer", "coral"]


class TTS:
    def __init__(self, out_dir: str, play: bool = False):
        self.out_dir = out_dir
        self.play = play
        os.makedirs(out_dir, exist_ok=True)
        self._idx = 0

    def synth(self, speaker: str, text: str, round_no: int):
        voice = _VOICES[(int(speaker.lstrip("P")) - 1) % len(_VOICES)]
        path = os.path.join(self.out_dir, f"r{round_no}_{speaker}_{self._idx}.mp3")
        self._idx += 1
        try:
            resp = get_client().audio.speech.create(
                model="tts-1", voice=voice, input=text)
            resp.stream_to_file(path)
            print(f"    [TTS] {speaker}Message synthesized to speech (voice {voice}）→ {path}")
            if self.play:
                #macOS comes with afplay; for other platforms, please change the player yourself
                subprocess.run(["afplay", path], check=False)
        except Exception as e:
            print(f"    [TTS] Synthesis failed (does not affect game progress):{e}")
