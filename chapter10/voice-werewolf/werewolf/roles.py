# -*- coding: utf-8 -*-
"""Role definitions, factions, and strategy prompts for each role.

The core of Werewolf is **information asymmetry**: different roles inherently know different information and have different
night actions. Here we centrally define the metadata and prompts for each role, which agent.py uses to construct each player
Agent's system prompt.
"""

from enum import Enum


class Role(str, Enum):
    """The four roles in the game."""
    WEREWOLF = "Werewolf"
    SEER = "Seer"
    WITCH = "Witch"
    VILLAGER = "Villager"


class Faction(str, Enum):
    """Two factions. The Seer, Witch, and Villager belong to the Good faction (Good = Special roles + Commoners)."""
    WEREWOLF = "Werewolf faction"
    GOOD = "Good faction"


# Role -> Faction
ROLE_FACTION = {
    Role.WEREWOLF: Faction.WEREWOLF,
    Role.SEER: Faction.GOOD,
    Role.WITCH: Faction.GOOD,
    Role.VILLAGER: Faction.GOOD,
}


# Strategy prompts for each role (corresponding to the "Agent Reasoning and Strategy" section in the book).
ROLE_STRATEGY = {
    Role.WEREWOLF: (
        "You are a werewolf. Your goal is to hide your identity, mislead the good, and ultimately ensure that the number of werewolves is not less than the good.\n"
        "Strategy: Speak like an ordinary villager; you can express reasonable suspicion of certain players, but do not be too aggressive to avoid exposure.\n"
        "If a Seer claims to have checked you as a werewolf, you can consider counterattacking them as a fake Seer who is jumping out.\n"
        "When voting, try to follow the majority of good players to avoid being an outlier. Never actively expose yourself or your teammates as werewolves."
    ),
    Role.SEER: (
        "You are the Seer (Good faction). Each night you can check the true faction (Good/Werewolf) of one player.\n"
        "Strategy: At an appropriate time (usually when you find a werewolf or the situation is critical), jump out to reveal your identity and check results to lead the good.\n"
        "If someone claims to be the Seer, compare the check information of both sides and point out contradictions or inconsistencies in the other's logic.\n"
        "Your check result is your unique key information; only you know it. Use it wisely to guide voting."
    ),
    Role.WITCH: (
        "You are the Witch (Good faction). You have one antidote and one poison, each usable only once.\n"
        "The antidote can save a player killed by werewolves at night; the poison can kill a player you suspect at night.\n"
        "Strategy: The antidote is usually reserved for key good players (e.g., the Seer) or not wasted early; use the poison when you are fairly sure someone is a werewolf.\n"
        "Your usage information is known only to you. During the day, be careful to protect yourself and do not easily reveal your identity as the Witch."
    ),
    Role.VILLAGER: (
        "You are a Villager (Good faction), with no night skills. You can only rely on logical reasoning to find werewolves.\n"
        "Strategy: Analyze whether each player's speech is self-consistent; watch out for players who rush to lead the rhythm, obscure their identity, or frequently change their stance.\n"
        "Pay attention to voting behavior—werewolves often concentrate their votes on the player most threatening to the good.\n"
        "Do not suspect randomly; every inference should be based on specific speech and voting facts."
    ),
}


def faction_of(role: Role) -> Faction:
    """Return the faction to which a given role belongs."""
    return ROLE_FACTION[role]
