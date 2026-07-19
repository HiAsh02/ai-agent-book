# -*- coding: utf-8 -*-
"""Player Agent: Each player = an independent LLM Agent with **strictly isolated private context**.

Key points for information isolation:
- Each PlayerAgent only maintains its own `memory` (a sequence of events it "observed / was told").
- The judge (judge.py) decides which information to push into which Agent's memory—only werewolves receive "teammate identities", only the seer receives "investigation results", and only public statements are pushed to everyone.
- When an Agent thinks (speaks / votes / uses abilities), it can only see the content in its own memory, so it cannot "peek" at information it should not see. This is the implementation of information access control.

Offline (--offline / --mock) strategy: When there is no OpenAI Key, or when you want to run a full game at zero cost and reproducibly, the Agent uses a **rule-driven** decision instead of LLM. The key point: the offline strategy also **only reads its own memory** (does not touch other Agents' private contexts), so the teaching point of information access control still holds and can be audited and verified in offline mode.
"""

import json
import os
import re
from typing import List, Optional

from .roles import Role, ROLE_STRATEGY, faction_of


# Global singleton LLM client. Default model is currently the cheap flagship gpt-5.6-luna.
# General fallback: prefer OPENAI_API_KEY to connect directly to OpenAI; otherwise use OPENROUTER_API_KEY to go through OpenRouter.
_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")
_client = None


def _to_openrouter_model(model: str) -> str:
    """ Map model name to OpenRouter namespace (for fallback path without OPENAI_API_KEY)."""
    if "/" in model:
        return model                      # Already an OpenRouter namespace, use as-is
    if model.startswith("gpt-"):
        return "openai/" + model          # gpt-* -> openai/gpt-*
    if model.startswith("claude-"):
        return "anthropic/claude-opus-4.8"
    return "openai/gpt-5.6-luna"          # Fallback: current cheap flagship


def _safe_create(client, **kwargs):
    """ Call Chat Completions; for reasoning models (e.g., gpt-5.x), automatically degrade and retry with parameter restrictions:
    - If max_tokens is not supported, use max_completion_tokens instead;
    - If non-default temperature is not supported, remove that parameter (fallback to model default 1).
    This way, the same code can run both traditional chat models (accepting temperature=0.8) and reasoning models."""
    for _ in range(3):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            msg = str(e)
            if "max_completion_tokens" in msg and "max_tokens" in kwargs:
                kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
                continue
            if "temperature" in msg and "temperature" in kwargs:
                kwargs.pop("temperature", None)
                continue
            raise
    return client.chat.completions.create(**kwargs)


def get_client():
    """ Return the globally shared LLM client (lazy-loaded, process-wide singleton).

    Only used in online mode (real LLM calls); offline mode does not import openai or construct a client.
      1) If OPENAI_API_KEY is set -> connect directly to OpenAI;
      2) Otherwise if OPENROUTER_API_KEY is set -> go through OpenRouter and map _MODEL to its namespace;
      3) If neither is set, raise a clear error.
    """
    global _client, _MODEL
    if _client is None:
        from openai import OpenAI  # Lazy import: offline mode does not need openai
        if os.environ.get("OPENAI_API_KEY"):
            _client = OpenAI()  # Automatically read environment variable OPENAI_API_KEY
        elif os.environ.get("OPENROUTER_API_KEY"):
            _MODEL = _to_openrouter_model(_MODEL)
            _client = OpenAI(
                api_key=os.environ["OPENROUTER_API_KEY"],
                base_url="https://openrouter.ai/api/v1",
            )
        else:
            raise RuntimeError(
                "Neither OPENAI_API_KEY nor OPENROUTER_API_KEY is set. Please refer to env.example for configuration, "
                "or switch to offline mode: python demo.py --offline"
            )
    return _client


class PlayerAgent:
    """A player Agent, encapsulating its identity, private context, and decision (LLM or offline rules)."""

    def __init__(self, name: str, role: Role, offline: bool = False, rng=None):
        self.name = name          # Player name, e.g., "P3"
        self.role = role          # Real identity (only known to the player and the judge)
        self.faction = faction_of(role)
        self.alive = True
        self.offline = offline    # When True, use rule-based strategy instead of LLM (zero cost, reproducible)
        # Private random source for offline strategy (seeded by player name for reproducibility and independence)
        import random as _random
        self._rng = rng or _random.Random(hash(name) & 0xFFFF)
        # Private context: all information this Agent can "see". Other Agents cannot access it.
        self.memory: List[str] = []

    # ---- Context injection: only the judge calls this to deliver information into this Agent's private context ----
    def observe(self, event: str):
        """Write a piece of information into this Agent's private context."""
        self.memory.append(event)

    # ---- System prompt: role setting + strategy. Teammate identities of werewolves are not written here; instead, the judge
    #      delivers them via observe() at game start, so the audit can record "who saw teammate identities". ----
    def _system_prompt(self, players: List[str]) -> str:
        return (
            f"You are playing a game of Werewolf. You are player {self.name}。\n"
            f"Your real identity is [{self.role.value}], belonging to [{self.faction.value}】。\n"
            f"There are {len(players)} players in this game: {'、'.join(players)}。\n\n"
            f"{ROLE_STRATEGY[self.role]}\n\n"
            "Important: Only reason based on the information you know; do not fabricate identities you cannot know. Speak like a real person, "
            "concise and natural, with reasoning and evidence."
        )

    def _context_block(self) -> str:
        """Concatenate the private context into a piece of text for the LLM."""
        if not self.memory:
            return "(No information yet)"
        return "\n".join(f"- {m}" for m in self.memory)

    def _chat(self, instruction: str, players: List[str], max_tokens: int,
              json_mode: bool = False) -> str:
        """Assemble system + user messages and call the LLM; the user message only concatenates this Agent's own
        private context (`_context_block`), never containing private information of other players."""
        messages = [
            {"role": "system", "content": self._system_prompt(players)},
            {"role": "user", "content":
                f"[Information you currently have (visible only to you)]\n{self._context_block()}\n\n"
                f"[Current Task]\n{instruction}"},
        ]
        #  Allocate sufficient output budget for reasoning models (e.g., GPT-5.6 series): their internal reasoning tokens also count.
        # max_tokens, if the budget is too small, the content may be truncated to empty. Set a lower limit as a fallback.
        kwargs = dict(model=_MODEL, messages=messages, temperature=0.8,
                      max_tokens=max(max_tokens, 512))
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = _safe_create(get_client(), **kwargs)
        # content may be None (e.g., truncated); fall back to empty string and let the upper layer parse with degraded handling.
        return (resp.choices[0].message.content or "").strip()

    # ---------- Three external capabilities: speech / decision (select target) / voting ----------

    def speak(self, players: List[str]) -> str:
        """Speak publicly during the day. Return a speech text (public information)."""
        if self.offline:
            return self._offline_speak(candidates=[p for p in players if p != self.name])
        instruction = (
            "It's your turn to speak publicly during the day. Please combine the information you have and make a brief statement."
            "(2~4 sentences, within 60 characters). Consistent with your identity and strategy. Output the speech content directly, without quotation marks."
        )
        return self._chat(instruction, players, max_tokens=180)

    def choose_target(self, prompt: str, candidates: List[str],
                      players: List[str], allow_none: bool = False) -> Optional[str]:
        """Let the Agent select a target from the candidates (night kill / investigate / poison / save judgment, etc.).

        Return in JSON mode, robustly parse the target player name.
        """
        if self.offline:
            return self._offline_choose_target(candidates, allow_none)
        opt = ", or you can choose to give up (fill target with \"none\")" if allow_none else ""
        instruction = (
            f"{prompt}\nCandidate players:{'、'.join(candidates)}{opt}。\n"
            "Please only return JSON: {\"target\": \"player name or none\", \"reason\": \"one-sentence reason\"}"
        )
        raw = self._chat(instruction, players, max_tokens=120, json_mode=True)
        target = self._parse_target(raw, candidates, allow_none)
        return target

    def vote(self, candidates: List[str], players: List[str]) -> Optional[str]:
        """Vote to banish. Return who to vote for (or abstain with none)."""
        if self.offline:
            return self._offline_vote(candidates)
        instruction = (
            "It is now the daytime voting and banishment phase. Based on all the speeches and your reasoning, vote for the one you think is most likely to be"
            "Werewolf player.\nCandidate players:" + "、".join(candidates) + "。\n"
            "Please return only JSON: {\"target\": \"player name\", \"reason\": \"one-sentence reason\"}"
        )
        raw = self._chat(instruction, players, max_tokens=120, json_mode=True)
        return self._parse_target(raw, candidates, allow_none=True)

    # ---------- Offline (rule-based) strategy: only read own memory, never access others' context ----------
    def _known_teammates(self) -> set:
        """The werewolf parses the list of teammates from its own private context (the good guys cannot parse it and return empty)."""
        mates = set()
        for m in self.memory:
            hit = re.search(r"Players in the werewolf faction are: ([^(]+)", m)
            if hit:
                mates |= set(re.findall(r"P\d+", hit.group(1)))
        return mates

    def _known_wolves(self) -> set:
        """Collect players who are 'known werewolves' from your own private context: the Seer's investigation results + the werewolves' teammates.

        Good ordinary villagers have no way of knowing anyone's identity → return an empty set, they can only vote randomly. This is precisely information asymmetry.
        """
        known = set(self._known_teammates())
        for m in self.memory:
            hit = re.search(r"You checked \s*(P\d+), the result is [Werewolf]", m)
            if hit:
                known.add(hit.group(1))
        return known

    def _offline_vote(self, candidates: List[str]) -> Optional[str]:
        """Offline voting: prioritize voting for 'confirmed werewolves' (seer's verification / werewolves not voting for teammates), otherwise random."""
        if not candidates:
            return None
        if self.role == Role.WEREWOLF:
            #  Werewolf: vote for a non-teammate good person, try to hide yourself
            mates = self._known_teammates()
            targets = [c for c in candidates if c not in mates] or candidates
            return self._rng.choice(targets)
        #  Good person: The Seer votes for the confirmed wolf if they have a result; otherwise, civilians can only vote randomly (the cost of information asymmetry).
        wolves = [c for c in candidates if c in self._known_wolves()]
        if wolves:
            return self._rng.choice(wolves)
        return self._rng.choice(candidates)

    def _offline_choose_target(self, candidates: List[str],
                               allow_none: bool) -> Optional[str]:
        """Offline night target selection: For mandatory scenarios like werewolf/seer, prioritize targets other than 'known werewolf';
        For optional scenarios like witch antidote/poison, decide based on probability."""
        if not candidates:
            return None
        if allow_none:
            # Witch's potion: about half probability to act (save/poison), making the game varied yet convergent.
            if self._rng.random() < 0.5:
                return None
            return self._rng.choice(candidates)
        if self.role == Role.SEER:
            #  Seer: Prioritize checking players whose identities have not yet been confirmed (avoid re-checking known werewolves).
            unknown = [c for c in candidates if c not in self._known_wolves()]
            return self._rng.choice(unknown or candidates)
        if self.role == Role.WEREWOLF:
            mates = self._known_teammates()
            targets = [c for c in candidates if c not in mates] or candidates
            return self._rng.choice(targets)
        return self._rng.choice(candidates)

    def _offline_speak(self, candidates: List[str]) -> str:
        """Offline speech: Generate a template utterance for a role that fits their identity and does not reveal private information."""
        wolves = [c for c in candidates if c in self._known_wolves()]
        suspect = self._rng.choice(candidates) if candidates else "Everyone"
        if self.role == Role.SEER and wolves:
            return f"I am the seer. Last night I checked {wolves[0]} is a werewolf. Please vote for him."
        if self.role == Role.WEREWOLF:
            return f"I am a good person. From the speech, {suspect} seems a bit suspicious. I suggest keeping an eye on him."
        if self.role == Role.WITCH:
            return f"I'll wait and see for now. I think {suspect}'s speech is untenable. Let's keep an eye on it first."
        if self.role == Role.SEER:
            return "I don't have decisive information yet. Let's listen to everyone's speeches and vote carefully."
        return f"I am a villager. I have no nighttime information, so I can only rely on reasoning. I feel {suspect} is slightly suspicious."

    # ---------- Parsing Tools ----------
    @staticmethod
    def _parse_target(raw: str, candidates: List[str], allow_none: bool) -> Optional[str]:
        target = None
        try:
            data = json.loads(raw)
            target = str(data.get("target", "")).strip()
        except Exception:
            # Fallback: Directly find candidate player names from text using regex
            target = raw
        if allow_none and target.lower() in ("none", "", "Abstain", "Abandon"):
            return None
        # Normalization: Exact match first, otherwise fuzzy match (find candidate names that appear)
        if target in candidates:
            return target
        for c in candidates:
            if c in (target or ""):
                return c
        # Final fallback: Search for Pn in the original string
        m = re.search(r"P\d+", target or "")
        if m and m.group(0) in candidates:
            return m.group(0)
        # If parsing fails: Good people default to abstain, werewolves/mandatory scenarios are handled by the caller
        return None if allow_none else (candidates[0] if candidates else None)
