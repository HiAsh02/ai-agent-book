# -*- coding: utf-8 -*-
"""Judge (Host) Agent: Code-driven game orchestration and information permission control hub.

The Judge is not an LLM—it is a **deterministic orchestrator** responsible for:
1. Maintaining centralized game state (identities, factions, life/death, phases, history).
2. **Information permission control**: deciding which information is delivered to each player Agent's private context
   (only werewolves know their teammates, only the Seer knows investigation results, public speeches go to everyone), and logging for audit.
3. Orchestrating day-night cycles: Night (werewolf kill → Seer investigate → Witch use potion) → Day (announce deaths →
   sequential speeches → vote to banish) → Determine win/loss.
"""

import random
from collections import Counter
from typing import List, Optional

from .agent import PlayerAgent
from .audit import AuditLog
from .roles import Role, Faction


def build_roles(players: int = 7, wolves: Optional[int] = None) -> List[Role]:
    """Derive identity composition from total player count: default 7 players = 2 werewolves + 1 Seer + 1 Witch + 3 Villagers.

    - If wolves is not specified, estimate as max(1, players // 3) (7 players gives 2 wolves, consistent with the book default).
    - For 4 or more players, assign 1 Seer; for 5 or more, additionally assign 1 Witch; the rest are all Villagers.
    """
    if players < 3:
        raise ValueError("Total player count must be at least 3")
    wolves = wolves if wolves is not None else max(1, players // 3)
    seer = 1 if players >= 4 else 0
    witch = 1 if players >= 5 else 0
    villagers = players - wolves - seer - witch
    if wolves < 1 or villagers < 0:
        raise ValueError(
            f"Illegal identity composition: {players} players cannot accommodate {wolves} wolves + {seer} Seers + "
            f"{witch} Witches (remaining villagers {villagers}). Please reduce --wolves or increase --players.")
    return ([Role.WEREWOLF] * wolves + [Role.SEER] * seer
            + [Role.WITCH] * witch + [Role.VILLAGER] * villagers)


def create_players(seed: int = 42, players: int = 7, wolves: Optional[int] = None,
                   offline: bool = False) -> List[PlayerAgent]:
    """Create a game instance (default 7 players: 2 werewolves + 1 Seer + 1 Witch + 3 Villagers, for cost control).

    Identities are randomly shuffled and assigned to P1~Pn, ensuring different identity distributions per game but reproducible with a seed.
    When offline=True, each Agent uses rule-based strategies instead of LLM (zero cost, reproducible); each Agent also receives an independent random source seeded by the seed and its index, ensuring fully reproducible offline games.
    """
    rng = random.Random(seed)
    roles = build_roles(players, wolves)
    rng.shuffle(roles)
    return [PlayerAgent(f"P{i+1}", roles[i], offline=offline,
                        rng=random.Random(seed * 1000 + i))
            for i in range(len(roles))]


class Judge:
    """Judge: orchestration + information permission control."""

    def __init__(self, players: List[PlayerAgent], seed: int = 42,
                 tts=None, max_rounds: int = 6):
        self.players = players
        self.names = [p.name for p in players]
        self.audit = AuditLog()
        self.rng = random.Random(seed + 1)
        self.tts = tts                 # Optional TTS synthesizer (injected when --voice is set)
        self.max_rounds = max_rounds
        self.round_no = 0
        self.phase = "Initialize"
        # Witch potion state
        self.witch_heal_available = True
        self.witch_poison_available = True

    # ------------------------------------------------------------------
    # Information delivery primitives: each primitive simultaneously (a) writes to the corresponding Agent's private context;
    #               (b) logs in the audit trail that 'this information entered whose context'.
    # ------------------------------------------------------------------
    def _log(self, category, content, visible_to):
        self.audit.add(self.round_no, self.phase, category, content, visible_to)

    def broadcast(self, category: str, content: str):
        """Public information: enters the context of **all players** (including eliminated ones)."""
        for p in self.players:
            p.observe(content)
        self._log(category, content, self.names)

    def private_send(self, player: PlayerAgent, category: str, content: str):
        """Private information: enters the context of **only the specified single player**."""
        player.observe(content)
        self._log(category, content, [player.name])

    def wolves_send(self, category: str, content: str):
        """Werewolf-exclusive information: enters the context of **only all werewolves**."""
        wolves = self.wolves()
        for w in wolves:
            w.observe(content)
        self._log(category, content, [w.name for w in wolves])

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------
    def alive(self) -> List[PlayerAgent]:
        return [p for p in self.players if p.alive]

    def wolves(self, alive_only=False) -> List[PlayerAgent]:
        ws = [p for p in self.players if p.role == Role.WEREWOLF]
        return [w for w in ws if w.alive] if alive_only else ws

    def by_name(self, name: str) -> Optional[PlayerAgent]:
        for p in self.players:
            if p.name == name:
                return p
        return None

    # ------------------------------------------------------------------
    # Phase 0: Assign identities and deliver initial 'who knows whom' information
    # ------------------------------------------------------------------
    def assign_identities(self):
        self.phase = "Identity assignment"
        print("\n" + "#" * 78)
        print("[Phase 0 · Identity Assignment] The Judge privately informs each player of their identity; werewolves are additionally told who their teammates are.")
        print("   Information isolation: each player only knows their own identity; only werewolves have 'teammate identities' in their context.")
        print("#" * 78)
        # Each player privately knows their own identity (only enters their own context)
        for p in self.players:
            self.private_send(p, "Identity assignment", f"Your identity is: {p.role.value}")
        # Werewolves know who their teammates are (only enters werewolf context)—this is the key to information asymmetry
        wolves = self.wolves()
        team = "、".join(w.name for w in wolves)
        self.wolves_send("Werewolf teammate identities", f"Players in the werewolf faction are: {team}(You are teammates and act together at night)")
        #  Print the real identity table (this is a 'God's perspective', for human observation only, not entering any Agent context)
        print("  [God's perspective / Human-only] Real identity table:")
        for p in self.players:
            print(f"    {p.name}: {p.role.value}（{p.faction.value}）")
        print(f"  Wolf teammates (only werewolf {team} has this information in their context)")

    # ------------------------------------------------------------------
    #  Night
    # ------------------------------------------------------------------
    def night(self) -> List[str]:
        """Execute a night phase and return the list of players eliminated tonight."""
        self.phase = "  Night"
        print("\n" + "=" * 78)
        print(f"  [Round {self.round_no} · Night] The night falls, close your eyes.")
        print("  Information isolation: all actions and results below are private—werewolf consensus only enters werewolf context,")
        print("  seer's investigation result only enters seer context, witch's potion use only enters witch context.")
        print("=" * 78)

        killed = self._wolves_act()
        self._seer_act()
        poisoned, saved = self._witch_act(killed)

        #  Settle tonight's deaths: killed by wolves and not saved + poisoned
        deaths = []
        if killed and not saved:
            deaths.append(killed)
        if poisoned and poisoned not in deaths:
            deaths.append(poisoned)
        for name in deaths:
            self.by_name(name).alive = False
        return deaths

    def _wolves_act(self) -> Optional[str]:
        wolves = self.wolves(alive_only=True)
        if not wolves:
            return None
        #  Candidates: all surviving non-werewolves (werewolves do not kill their own)
        candidates = [p.name for p in self.alive() if p.role != Role.WEREWOLF]
        if not candidates:
            return None
        votes = []
        for w in wolves:
            t = w.choose_target(
                "  It is night, werewolves act. Please agree with your teammates and choose a good player to kill tonight.",
                candidates, self.names, allow_none=False)
            if t:
                votes.append(t)
                print(f"  [Judge + Werewolf only] Werewolf {w.name} proposes to kill → {t}")
        if not votes:
            return None
        #  Summary: highest votes; tie goes to the first werewolf's opinion
        tally = Counter(votes)
        top = tally.most_common()
        best = [n for n, c in top if c == top[0][1]]
        killed = votes[0] if len(best) > 1 else top[0][0]
        #  Write 'tonight's werewolf consensus' into the werewolf shared context (only werewolves can see it)
        self.wolves_send("  Werewolf night consensus", f"  Round{self.round_no} night, werewolves decide to kill {killed}")
        print(f"  → Werewolf consensus: kill {killed} (this consensus only enters werewolf context)")
        return killed

    def _seer_act(self):
        seers = [p for p in self.alive() if p.role == Role.SEER]
        if not seers:
            return
        seer = seers[0]
        candidates = [p.name for p in self.alive() if p.name != seer.name]
        target = seer.choose_target(
            "  It is night, seer acts. Please choose a player to investigate their true faction.",
            candidates, self.names, allow_none=False)
        if not target:
            target = self.rng.choice(candidates)
        tgt = self.by_name(target)
        result = "  Werewolf" if tgt.role == Role.WEREWOLF else "  Good"
        #  Investigation result only enters the seer's own context—this is key information exclusive to the seer
        self.private_send(seer, "  Seer investigation result",
                          f"  Round{self.round_no}  Round you investigated {target}, result is 【{result}】")
        print(f"  [Judge + Seer only {seer.name} visible] Seer investigates {target} → {result}")

    def _witch_act(self, killed: Optional[str]):
        witches = [p for p in self.alive() if p.role == Role.WITCH]
        if not witches:
            return None, False
        witch = witches[0]
        saved = False
        poisoned = None

        # Inform the witch who was killed tonight (only enters witch's context)
        if killed:
            self.private_send(witch, "Witch's night info", f"  Round{self.round_no}Round, the player attacked by werewolves tonight is {killed}")
            print(f"  [Judge + Witch only {witch.name} visible] Witch learns who was killed tonight:{killed}")
            #  Antidote: whether to save
            if self.witch_heal_available and killed != witch.name:
                dec = witch.choose_target(
                    f"Tonight {killed} was attacked by werewolves. Do you use the [Antidote] to save them?"
                    "(If saving, fill target with the player's name; if not, fill none)",
                    [killed], self.names, allow_none=True)
                if dec == killed:
                    saved = True
                    self.witch_heal_available = False
                    self.private_send(witch, "Witch uses potion", f"You used the antidote in round {self.round_no}, saving {killed}")
                    print(f"  [Judge + Witch only visible] Witch uses antidote to save {killed}")
        else:
            self.private_send(witch, "Witch's night info", f"  Round{self.round_no}Round is a peaceful night (no one was killed by werewolves, or you have no way of knowing)")

        #  Poison: whether to poison someone
        if self.witch_poison_available:
            candidates = [p.name for p in self.alive() if p.name != witch.name]
            dec = witch.choose_target(
                "Do you use the [Poison] to kill a player you suspect is a werewolf? (If poisoning, fill the player's name; if not, fill none)",
                candidates, self.names, allow_none=True)
            if dec and dec in candidates:
                poisoned = dec
                self.witch_poison_available = False
                self.private_send(witch, "Witch uses potion", f"You used the antidote in round {self.round_no}Round used poison, killing {poisoned}")
                print(f"  [Judge + Witch only visible] Witch uses poison to kill {poisoned}")
        return poisoned, saved

    # ------------------------------------------------------------------
    #  Daytime
    # ------------------------------------------------------------------
    def day(self, night_deaths: List[str]) -> Optional[str]:
        """Daytime: Announce deaths → Speak in turn → Vote to banish. Return the name of the banished player (or None)."""
        self.phase = "Daytime"
        print("\n" + "=" * 78)
        print(f"  [Round {self.round_no} Round · Daytime] The sky is bright. Please open your eyes.")
        print("  Information isolation: Death announcements, speeches, and voting results are public information and enter everyone's context.")
        print("=" * 78)

        #  Announce deaths (public)
        if night_deaths:
            msg = f"Day has dawned. The players eliminated last night are:{'、'.join(night_deaths)}"
        else:
            msg = "Day has dawned. Last night was a peaceful night, no one was eliminated"
        self.broadcast("Public - Death announcement", msg)
        print(f"  Judge announces:{msg}")

        if self._check_winner():
            return None

        #  Speak in turn (public)
        print("\n  —— Speech phase (in seat order, public speech enters everyone's context) ——")
        for p in self.alive():
            speech = p.speak(self.names)
            line = f"{p.name} (speak):{speech}"
            self.broadcast("Public speech", f"{p.name}  says:{speech}")
            print(f"  {line}")
            if self.tts:  #  Optional: synthesize speech
                self.tts.synth(p.name, speech, self.round_no)

        #  Vote to banish (public)
        print("\n  —— Voting phase ——")
        exiled = self._vote()
        return exiled

    def _vote(self) -> Optional[str]:
        alive = self.alive()
        tally = Counter()
        for p in alive:
            candidates = [q.name for q in alive if q.name != p.name]
            t = p.vote(candidates, self.names)
            if t:
                tally[t] += 1
                print(f"  {p.name}  Vote → {t}")
            else:
                print(f"  {p.name}  Abstain")
        if not tally:
            self.broadcast("Public-Banish", "No one was banished this round (all abstained)")
            print("  No one was banished this round")
            return None
        top = tally.most_common()
        best = [n for n, c in top if c == top[0][1]]
        exiled = self.rng.choice(best) if len(best) > 1 else top[0][0]
        ex = self.by_name(exiled)
        ex.alive = False
        result = f"Vote result:{exiled}  was banished, their true identity is [{ex.role.value}]. Vote count:" + \
                 "，".join(f"{n}={c} votes" for n, c in top)
        self.broadcast("Public-Banish", result)
        print(f"  → {result}")
        return exiled

    # ------------------------------------------------------------------
    #  Settlement
    # ------------------------------------------------------------------
    def _check_winner(self) -> Optional[Faction]:
        """Determine if the game has ended: if all werewolves are eliminated, good wins; if werewolves >= good players, werewolves win;
        otherwise return None (continue game)."""
        w = len(self.wolves(alive_only=True))
        g = len([p for p in self.alive() if p.role != Role.WEREWOLF])
        if w == 0:
            return Faction.GOOD
        if w >= g:  #  Werewolves >= good players → werewolves win (simplified kill-all rule)
            return Faction.WEREWOLF
        return None

    def run(self) -> Faction:
        """Run a full game and return the winning faction."""
        self.assign_identities()
        winner = None
        while winner is None and self.round_no < self.max_rounds:
            self.round_no += 1
            deaths = self.night()
            winner = self._check_winner()
            if winner:
                break
            self.day(deaths)
            winner = self._check_winner()
        if winner is None:
            #  Reached round limit, determine by number of survivors (more good players means good wins)
            winner = self._check_winner() or Faction.GOOD
        self._announce(winner)
        return winner

    def _announce(self, winner: Faction):
        self.phase = "Settlement"
        print("\n" + "#" * 78)
        print("[Game Over · Settlement]")
        alive = [f"{p.name}({p.role.value})" for p in self.alive()]
        print(f"  Surviving players:{'、'.join(alive) if alive else 'None'}")
        print(f"  >>> Winning faction:{winner.value} <<<")
        print("#" * 78)
