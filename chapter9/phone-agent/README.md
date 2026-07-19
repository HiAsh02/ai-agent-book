# Experiment 9-2: Building a Phone Agent with the PineClaw Voice API

Accompanying Chapter 9, Experiment 9-2 of "Deep Understanding of AI Agents".

## Objective

Many real-world agent tasks require **making actual phone calls**—contacting customer service to negotiate a bill, booking a restaurant, or confirming an order. This experiment demonstrates an important application direction for voice agents: **The agent can not only engage in voice conversations with users but also interact with the outside world via phone calls on the user's behalf**.

The top layer is a standard **ReAct Agent**: given a natural language task (e.g., "Call the broadband customer service, ask why my bill was overcharged by 50 yuan this month, and request an explanation"), it figures out the number to dial, the call goal, and the context, invokes the `make_phone_call` tool to complete the entire call, reads the returned **structured call record**, asks follow-up questions or redials if necessary, and finally reports the result to the user.

## Abstraction of the Phone Voice API

A production-grade phone voice API (such as the [PineClaw Voice API](https://pineclaw.com/), developed by the author's team) encapsulates an entire phone call as **a single tool call**:

```
record = make_phone_call(phone_number, goal, context)
```

You only provide three things—**number, goal, context**—and its voice agent automatically handles:

- **Dialing**: Connecting to the callee;
- **IVR Navigation**: Handling menu prompts like "Press 1 for billing, press 0 for an operator";
- **Multi-turn Conversation**: Negotiating, asking follow-ups, and confirming key information around the goal once connected to a human;
- **Transcription**: Converting the entire call into text.

Finally, it returns a **structured call record**, not a raw audio recording. This is precisely why it can fit into a ReAct loop: the agent receives structured fields (whether the goal was achieved, extracted key information, turn-by-turn transcript) and can make decisions and report based on them directly. The shape of the return body in this experiment (see `CallRecord` in `pine_voice.py`):

| Field | Description |
| --- | --- |
| `call_id` | Unique call ID |
| `phone_number` / `goal` | Phone number and goal of this call |
| `status` / `goal_achieved` | Call status / whether the goal was achieved |
| `duration_seconds` | Call duration |
| `summary` | One-sentence call summary |
| `key_fields` | Extracted key information (deduction reason / amount / confirmation number / time…) |
| `transcript` | Turn-by-turn conversation `[{speaker, text}, ...]` |
| `follow_up_needed` / `follow_up_reason` | Whether a follow-up is needed and the reason |

## About the Mock (Important)

The real PineClaw Voice API requires a `PINECLAW_API_KEY` and will dial real phone numbers. To facilitate offline execution, this experiment **uses a local mock client instead of the real API** (`pine_voice.py`):

- It **does not touch the real phone network** and **does not require a PineClaw key**;
- Internally, `make_phone_call` uses **OpenAI to play the role of the callee**—first acting as an automated IVR voice menu, then as a human customer service agent after being "transferred"—engaging in a **multi-turn conversation** (simulating IVR navigation + customer service response) with the outgoing voice agent, then summarizing the transcript into the structured record shown in the table above;
- The key point: **The mock client has exactly the same input/output contract as the real API**, so the code of the upper-layer ReAct Agent requires almost no changes when switching to the real PineClaw SDK.

Therefore, the "deduction reason," "confirmation number," etc., appearing in this experiment are **simulated scenarios fabricated on the fly by the model**, used only to demonstrate the data flow and do not represent any real calls.

### Real Integration with PineClaw

Simply replace the call to the mock `make_phone_call` in `agent.py` with the real SDK; the rest of the logic remains unchanged:

```python
# pip install pine-voice
from pine_voice import PineVoiceClient   # Real SDK (illustrative)

client = PineVoiceClient(api_key=os.environ["PINECLAW_API_KEY"])

def make_phone_call(phone_number, goal, context=""):
    call = client.calls.create(to=phone_number, goal=goal, context=context)
    result = call.wait()          # Blocks until the call ends (could be minutes to hours)
    return result.to_dict()       # Returns a structured call record of the same shape
```

For real usage, please refer to the official PineClaw documentation; it is recommended to first dial **your own phone** to verify connectivity.

## Running

```bash
cd chapter9/phone-agent
pip install -r requirements.txt

cp env.example .env
# Edit .env, fill in OPENROUTER_API_KEY or OPENAI_API_KEY (at least one)

python demo.py
python demo.py --task "Call the restaurant to book a table for 4 at 7 PM tonight"   # Custom phone task
python demo.py --dry-run                                       # Run offline, no API Key required
python demo.py --help                                          # View all parameters
```

Command-line arguments (`python demo.py --help` has Chinese descriptions):

| Argument | Description |
| --- | --- |
| `--task` | Custom phone task (natural language). Defaults to the broadband bill example from the book |
| `--phone` | Optional: The callee's phone number. Provided as known info to the agent (used directly as the callee number in dry-run mode) |
| `--goal` | Optional: A clear call goal. Provided as known info to the agent (used directly as the call goal in dry-run mode) |
| `--model` | Optional: Override the model (defaults to `OPENAI_MODEL`, i.e., `gpt-5.6-luna`) |
| `--dry-run` | **Offline script mode**: No internet connection, no API Key required, only demonstrates the shape of the ReAct loop and data contract |

`demo.py` will actually call OpenAI (unless `--dry-run` is added) and print three sections:
(a) The ReAct Agent's trace (thinking + initiating `make_phone_call`);
(b) The returned structured call record (multi-turn transcript + whether the goal was achieved + key fields);
(c) The agent's final report to the user based on the call result.

> **Model and Fallback**: The default chat model is `gpt-5.6-luna`. The resolution priority is
> `OPENAI_API_KEY` (optionally `OPENAI_BASE_URL` pointing to a compatible gateway, such as Moonshot `kimi-k3` / Volcano Ark)
> \> `OPENROUTER_API_KEY` (automatically maps the model to `openai/gpt-5.6-luna` etc. in `provider/model` format).
> Since `gpt-5.6*` requires organizational real-name authentication for direct connection to OpenAI, **OpenRouter is recommended**; just fill in
> `OPENROUTER_API_KEY` in `.env` (do not set `OPENAI_API_KEY` in this case, otherwise direct connection will take priority).

### Difference Between the Two Levels of "Mock"

There are two independent layers of simulation in this experiment; do not confuse them:

- **Default (mock)**: `pine_voice.py` replaces the real **phone network**, but the conversation between the ReAct Agent and the callee is still **generated in real-time by OpenAI**—so an `OPENAI_API_KEY` is required, and each conversation/field will be different.
- **`--dry-run` (offline script)**: The LLM is not called at all; `make_phone_call` directly returns a **fixed script** of a structured call record. Used to run through the entire ReAct loop (think → call tool → read structured record → report) and see its shape **without any API Key, completely offline**. The confirmation number in the script is derived from the hash of the goal, is reproducible, and **does not represent any real call**.

## Expected Output Example (Real Excerpt)

```
[Agent calls tool make_phone_call] Parameters:
    phone_number = 10010
    goal         = Inquire about the reason for the extra 50 yuan on this month's broadband bill and request a refund for the erroneous charge.
    context      = Broadband account hz-88231

[PineClaw returns structured call record]
  Status           : completed  |  Goal Achieved: True
  Summary          : The user successfully inquired about the reason for the extra 50 yuan on the broadband bill and applied for a refund.
  Key Fields (key_fields):
      - Deduction Reason: System automatically adjusted the plan fee
      - Amount Involved: 50 yuan
      - Confirmation Number: RW20231015
      - Processing Result: Refund application successfully submitted
  Call Transcript (transcript):
      << [Callee] Welcome to customer service hotline! For billing inquiries, press 1; for business processing, press 2; for a human operator, press 0.
      >> [Voice Agent] I'll press 0 to be transferred to a human.
      << [Callee] Hello, I am a customer service representative, employee ID 12345. How can I help you?
      >> [Voice Agent] Hi, I noticed an extra 50 yuan on my broadband bill. Can you help me check the reason? My account is hz-88231.
      ...(Multiple rounds of negotiation, verification, confirmation number provided)...

Agent's final report to the user:
  Successfully called customer service and inquired about the reason: Deduction reason = System automatically adjusted the plan fee; refund submitted, confirmation number RW20231015.
```

Note: The IVR menu, employee ID, confirmation number, etc., are **simulated scenarios fabricated on the fly by the model** (see "About the Mock"), used only to demonstrate the data flow; the conversation and fields will differ with each run, but the shape of "IVR navigation → transfer to human for multi-turn negotiation → structured record → agent report" is stably reproduced.

## File Descriptions

| File | Description |
| --- | --- |
| `pine_voice.py` | Local **mock** client for the PineClaw Voice API, providing the `make_phone_call` tool |
| `agent.py` | **ReAct Agent** (OpenAI function calling) that uses `make_phone_call` as a tool |
| `demo.py` | End-to-end demonstration: from task assignment to reporting for a phone call |
| `requirements.txt` / `env.example` | Dependencies and environment variable template |
