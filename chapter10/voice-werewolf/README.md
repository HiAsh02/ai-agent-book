# Experiment 10-8: Voice Werewolf Agent System

Companion to Chapter 10 of "Understanding AI Agents" – Experiment 10-8: Voice Werewolf Agent System.

## Objective

Use a multi-agent Werewolf system to demonstrate a form of multi-agent collaboration that best embodies **non-shared context**—**Information Asymmetry**: different roles can only see the information they are supposed to see. The system consists of three parts:

1. **Multi-Agent**: Each player = an independent LLM Agent (Chat Completions, default `gpt-5.6-luna`), each maintaining **strictly isolated private contexts**, reasoning only based on the information they see.
2. **Information Access Control**: The **Judge** decides which information is delivered into which player Agent's context—wolves know their teammates, the Seer knows the investigation result, public speeches go to everyone. Each delivery is logged for auditing, and after the game ends, the audit table is printed and isolation is **automatically verified**.
3. **Judge Orchestration**: The Judge is a **code-driven** (non-LLM) deterministic orchestrator that manages the day/night cycle and determines the winner.

> **Voice is an optional enhancement, not required to run.** The default "text mode" is sufficient to run a complete, reproducible game and verify information isolation; add `--voice` to use OpenAI `tts-1` to synthesize public speeches into audio.

> **Offline mode (`--offline` / `--mock`): No API Key required, zero cost, fully reproducible.**
> In this mode, each player Agent uses a set of **rule-based strategies** instead of an LLM to make speech/vote/skill decisions. The key point is: the offline strategy also **only reads its own private context** (`memory`), never accessing other Agents' information—therefore, the core teaching point of information access control still holds in offline mode and can still pass audit verification.
> To see the full picture of "Judge orchestration + information isolation" at zero cost, use `python demo.py --offline`.

To control costs, this demo defaults to a **7-player game** (all played by AI, ensuring reproducibility and verifiability):
**2 Werewolves + 1 Seer + 1 Witch + 3 Villagers**; you can also customize with `--players` / `--wolves`.

## Role and Information Access Matrix

| Information Category | Who Can See (enters whose context) | Description |
|---|---|---|
| Own identity | Only oneself | Each person only knows their own role |
| **Werewolf teammate identities** | **Only all werewolves** | Werewolves know each other; good guys don't know anyone's identity |
| **Werewolf night consensus** | **Only all werewolves** | Tonight's kill target decision, only enters werewolf context |
| **Seer investigation result** | **Only the Seer** | Investigates one person's alignment each night, result is exclusive |
| **Witch night info / potion use** | **Only the Witch** | Who was killed tonight, whether to use healing/poison potion, exclusive |
| Death announcement (at dawn) | Everyone | Public information |
| Daytime speeches | Everyone | Public information, enters all player contexts |
| Voting and banishment result | Everyone | Public information, the banished player's identity is revealed |

The "God's perspective" true identity table is only printed for human observation, **not entered into any Agent context**.

## Judge Orchestration (Day/Night Cycle)

```
Phase 0 Assign identities: privately send each person their identity; only broadcast "teammate identities" to werewolves
Each round:
  Night: Werewolves collectively choose a kill target (werewolf consensus only enters werewolf context)
         → Seer investigates one person (result only enters Seer context)
         → Witch decides whether to use healing potion to save / poison potion to kill (only enters Witch context)
         → Settle tonight's deaths
  Check win condition; if not decided, proceed to daytime
  Daytime: Announce deaths (public)
           → Public speeches in seat order (enters everyone's context)
           → All players vote to banish, announce the banished player's identity (public)
  Check win condition
Win condition: All werewolves eliminated → Good guys win; Werewolf count ≥ Good guy count → Werewolves win (simplified slaughter rule)
```

## Running

```bash
pip install -r requirements.txt
cp env.example .env        # Fill in OPENAI_API_KEY; or directly export OPENAI_API_KEY=sk-...

# Offline mode: No API Key required, rule-based decisions, zero cost, reproducible, best to run first to see the full picture
python demo.py --offline

# Online mode (LLM decisions, requires OPENAI_API_KEY)
python demo.py             # Text mode, run a complete game (default, recommended)
python demo.py --seed 7    # Change the identity distribution (reproducible)
python demo.py --voice     # Additionally use OpenAI tts-1 to synthesize public speeches into audio/ directory
python demo.py --voice --play   # Synthesize and play (macOS afplay)
python demo.py --model gpt-5.6-luna   # Override model

# General parameters (available for both offline/online)
python demo.py --offline --players 9 --wolves 3   # Customize player count and werewolf count
python demo.py --offline --max-rounds 8           # Adjust round limit
python demo.py --offline --log game.log           # Save the complete game log to a file

python demo.py --help      # View all parameters (Chinese descriptions)
```

Running will print sequentially: each phase's process (with information isolation annotations showing "who can see what") → final winner →
**Information Visibility Audit Table** → **Information Isolation Automatic Verification** (showing the private contexts of werewolf/villager/seer sides, proving each sees only their own).

## File Description

```
voice-werewolf/
├── demo.py              # Entry point: run a complete game + print audit table + automatically verify information isolation
├── werewolf/
│   ├── roles.py         # Roles, alignments, strategy prompts for each role
│   ├── agent.py         # PlayerAgent: one Agent per player + private context + LLM/offline rule-based decision
│   ├── game.py          # Judge: Judge orchestration + information delivery primitives (with audit logging)
│   ├── audit.py         # Information visibility audit log
│   └── tts.py           # Optional voice synthesis (OpenAI tts-1)
├── requirements.txt
├── env.example
└── audio/               # Voice files synthesized when using --voice
```

The information isolation implementation is in `game.py`'s three delivery primitives: `broadcast` (enters everyone's context),
`private_send` (enters only one person's context), `wolves_send` (enters only werewolves' context); each primitive synchronously writes to the corresponding Agent's `memory` and logs in the audit "whose context it entered". Each Agent only reads its own `memory` when thinking, physically unable to see others' private information.

## Real Run Example (`python demo.py`, seed=42, gpt-5.6-luna)

Night (private actions, all with visibility annotations):

```
【Round 1 · Night】Close your eyes, it's night.
  [Visible only to Judge + Werewolves] Werewolf P1 proposes to kill → P3
  [Visible only to Judge + Werewolves] Werewolf P6 proposes to kill → P3
  → Werewolf consensus: kill P3 (this consensus only enters werewolf context)
  [Visible only to Judge + Seer P4] Seer investigates P1 → Werewolf
  [Visible only to Judge + Witch P2] Witch learns tonight's victim: P3
  [Visible only to Judge + Witch] Witch uses healing potion to save P3
```

Daytime: Seer P4 immediately reveals and reports the investigation (Round 1 daytime, public speech enters everyone's context):

```
  P4 (speech): I am the Seer, last night I investigated P1 and found them to be a Werewolf. The peaceful night does not affect the investigation result. Today, please prioritize voting for P1; if P1 counter-claims, ask them to explain their specific investigation information and logic.
  —— Voting Phase ——
  → Voting result: P1 is banished, their true identity is 【Werewolf】. Vote count: P1=5 votes, P4=2 votes
```

Round 2 night, the Seer investigates P6 and finds them to be a Werewolf, the Witch uses poison to kill P6. The good guys win after banishing/poisoning both werewolves (survivors: P2 Witch, P3 Villager, P5 Villager, P7 Villager).

Information Isolation Automatic Verification (excerpt):

```
[Check 1] 『Werewolf teammate identities』only enters werewolf context: Passed ✓
   - Any non-werewolf context contains teammate identities? False (should be False)
[Check 2] 『Seer investigation result』only enters Seer(P4) context: Passed ✓
   - Any other player context contains investigation result? False (should be False)
[Check 3] Visible set of werewolf-exclusive information in audit log == werewolf set ['P1', 'P6']: Passed ✓
[Check 4] Visible set of all 『public-*』information in audit log == all players: Passed ✓
Information isolation total check: All passed ✓✓✓
```

Comparison shows: Werewolf P1's context contains "Players in the werewolf faction are: P1, P6" and "Werewolves decide to kill P3", while Villager P3's context contains **no other player's identity**, and Seer P4's context **uniquely** contains "Round 1 you investigated P1, result is 【Werewolf】". This is direct evidence of information access control in effect.

## Limitations

- **Online mode LLM decisions** default to the cheap flagship `gpt-5.6-luna` (`OPENAI_API_KEY`). **General fallback**: If `OPENAI_API_KEY` is not set but `OPENROUTER_API_KEY` is set, it automatically switches to OpenRouter and maps the model name to its namespace (`gpt-5.6-luna` → `openai/gpt-5.6-luna`); note that the `gpt-5.6` series requires organization verification for direct OpenAI connection, setting only `OPENROUTER_API_KEY` will force using OpenRouter. Note: the optional voice synthesis (`--voice`, OpenAI tts-1) still only supports `OPENAI_API_KEY`, OpenRouter has no TTS endpoint.
  To run the full process at zero cost without any API Key, use `--offline` (rule-based decisions); the offline strategy is relatively simple, speech/reasoning is less vivid than LLM, only used to demonstrate the orchestration and information isolation mechanism, not representing real game-playing ability.
- For reproducibility and cost control, this demo **is entirely played by AI**, defaulting to text mode; the book's "real human voice connection" and real-time conversation are simplified here to: Judge orchestrates speeches in seat order, AI uses text for reasoning and voting, voice is only an optional one-way TTS output (`--voice`), without real human ASR voice input and real-time interruption.
- The win condition uses the "simplified slaughter rule" (Werewolf count ≥ Good guy count → Werewolves win), without implementing advanced mechanics like Hunter, Sheriff, self-destruct, etc.; the Witch's healing potion defaults to allowing self-rescue, all can be extended as needed.
- Each game result is random, length depends on AI reasoning (usually 2-4 rounds to determine the winner); use `--seed` to reproduce or switch game scenarios. AI's deception/reasoning quality is limited by model capability.
