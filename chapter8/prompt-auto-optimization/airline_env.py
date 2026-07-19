"""
Simplified version of the "Aviation Customer Service" simulation environment (comparable to the aviation scenario in tau-bench, but with reduced complexity).

It consists of three parts:
1. TOOLS      —— Tools exposed to the agent (including the critical transfer_to_human).
2. run_agent  —— A minimal agent with a tool-calling loop: given a system prompt and user request,
                 it returns whether to transfer to human and the final response.
3. CASES      —— Two sets of evaluation cases:
                 - Holdout task set: normal requests that the agent should handle correctly (should not transfer when not needed, and should transfer when necessary).
                 - Boundary case set: policy disputes where the agent should explain the policy rather than simply transferring.
"""

import json
from config import get_client, get_model, TEMPERATURE

# ----------------------------------------------------------------------------
# 1. Tool definitions (OpenAI function-calling format)
# ----------------------------------------------------------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup_reservation",
            "description": "Query passenger order details (flight, cabin, fare type, etc.) by order number.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_code": {"type": "string", "description": "Order number"}
                },
                "required": ["confirmation_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_flight",
            "description": "Process a rebooking for the passenger to a specified new flight.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_code": {"type": "string"},
                    "new_flight": {"type": "string", "description": "New flight number or date"},
                },
                "required": ["confirmation_code", "new_flight"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refund_policy",
            "description": "Query refund/cancellation policy. Input fare type (e.g., economy special fare/full-fare economy/business class).",
            "parameters": {
                "type": "object",
                "properties": {
                    "fare_type": {"type": "string", "description": "Fare type"}
                },
                "required": ["fare_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_baggage_policy",
            "description": "Query baggage allowance and excess baggage fee policy. Input cabin class.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cabin": {"type": "string", "description": "Cabin class, e.g., economy/business class"}
                },
                "required": ["cabin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "change_seat",
            "description": "Process seat selection or seat change for the passenger.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_code": {"type": "string"},
                    "seat": {"type": "string", "description": "Target seat number"},
                },
                "required": ["confirmation_code", "seat"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "Transfer the conversation to a human agent. After calling, the agent will no longer process the current request.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "Transfer reason"}
                },
                "required": ["reason"],
            },
        },
    },
]

# ----------------------------------------------------------------------------
# 2. Mock implementation of tools (returns fixed simulated data for the agent to compose responses)
# ----------------------------------------------------------------------------
_POLICY_REFUND = {
    "Economy special fare": "Economy special fare is non-refundable and does not support voluntary refunds; if not yet departed, taxes and fees such as fuel surcharge and airport construction fee can be refunded.",
    "Full-fare economy": "Full-fare economy can be refunded before departure with a 5% cancellation fee.",
    "Business class": "Business class can be fully refunded before departure with no fee.",
}


def _run_tool(name: str, args: dict) -> str:
    """Execute tool and return the string result to the model."""
    if name == "lookup_reservation":
        return json.dumps(
            {
                "confirmation_code": args.get("confirmation_code", "UNKNOWN"),
                "passenger": "Zhang Wei",
                "flight": "YS1234 Shanghai Hongqiao→Beijing Capital 2026-08-01 09:00",
                "cabin": "Economy class",
                "fare_type": "Economy special fare",
                "status": "Ticketed",
            },
            ensure_ascii=False,
        )
    if name == "change_flight":
        return json.dumps(
            {"result": "success", "new_flight": args.get("new_flight"), "fee": "Change fee 200 yuan"},
            ensure_ascii=False,
        )
    if name == "get_refund_policy":
        fare = args.get("fare_type", "Economy special fare")
        text = _POLICY_REFUND.get(fare, _POLICY_REFUND["Economy special fare"])
        return json.dumps({"fare_type": fare, "policy": text}, ensure_ascii=False)
    if name == "get_baggage_policy":
        cabin = args.get("cabin", "Economy class")
        free = "20kg" if "Economy" in cabin else "30kg"
        return json.dumps(
            {"cabin": cabin, "free_allowance": free, "excess_fee": "Excess baggage fee 50 yuan/kg"},
            ensure_ascii=False,
        )
    if name == "change_seat":
        return json.dumps(
            {"result": "success", "seat": args.get("seat")}, ensure_ascii=False
        )
    return json.dumps({"result": "ok"}, ensure_ascii=False)


# ----------------------------------------------------------------------------
# 3. Minimal agent loop
# ----------------------------------------------------------------------------
def run_agent(system_prompt: str, user_message: str, max_steps: int = 4) -> dict:
    """
    Run a customer service session. Returns:
      {
        "transferred": bool,        # Whether transfer_to_human was called
        "transfer_reason": str|None,
        "final_text": str,          # Agent's final reply to the passenger (empty if transferred)
        "tool_calls": [str, ...],   # Names of tools called in order
      }
    """
    client = get_client()
    model = get_model()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    tool_calls_log = []

    for _ in range(max_steps):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS,
            temperature=TEMPERATURE,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            # Model directly gives a text reply to the passenger — session ends
            return {
                "transferred": False,
                "transfer_reason": None,
                "final_text": msg.content or "",
                "tool_calls": tool_calls_log,
            }

        # There is a tool call, first add the assistant message to history
        messages.append(msg)

        transferred_now = False
        transfer_reason = None
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls_log.append(name)

            if name == "transfer_to_human":
                transferred_now = True
                transfer_reason = args.get("reason", "")
                result = json.dumps({"result": "transferred"}, ensure_ascii=False)
            else:
                result = _run_tool(name, args)

            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

        if transferred_now:
            return {
                "transferred": True,
                "transfer_reason": transfer_reason,
                "final_text": "",
                "tool_calls": tool_calls_log,
            }

    # Exceeded step limit without convergence, fallback to request a plain text reply again
    resp = client.chat.completions.create(
        model=model, messages=messages, temperature=TEMPERATURE
    )
    return {
        "transferred": False,
        "transfer_reason": None,
        "final_text": resp.choices[0].message.content or "",
        "tool_calls": tool_calls_log,
    }


# ----------------------------------------------------------------------------
# 4. Evaluation Cases
# ----------------------------------------------------------------------------
# Fields for each case:
#   id / group / user   —— user request
#   should_transfer     —— whether the correct behavior should transfer to human
#   rubric              —— when should_transfer=False, criteria for judging "proper handling"
CASES = [
    # ---------- Holdout task set: correct behavior exists, must not regress after optimization ----------
    {
        "id": "H1-Change Booking",
        "group": "holdout",
        "user": "Hello, my order number is ABC123. I want to change my flight from August 1 to August 3. Please help me change it.",
        "should_transfer": False,
        "rubric": "Query the order and handle/explain the change to August 3 (e.g., change fee) for the passenger, rather than transferring to human.",
    },
    {
        "id": "H2-Baggage Allowance",
        "group": "holdout",
        "user": "I bought economy class. What is the free checked baggage allowance? How is overweight charged?",
        "should_transfer": False,
        "rubric": "Provide specific policy information on economy class free baggage allowance and excess baggage fees, rather than transferring to human.",
    },
    {
        "id": "H3-Seat Selection",
        "group": "holdout",
        "user": "Order number ABC123, I want to switch to window seat 32A.",
        "should_transfer": False,
        "rubric": "Handle/confirm the switch to seat 32A for the passenger, rather than transferring to human.",
    },
    {
        "id": "H4-Explicitly Request Human",
        "group": "holdout",
        "user": "Stop messing around, I want to talk to a human agent. Transfer me to a human right now.",
        "should_transfer": True,  # Passenger explicitly requests human — this should be transferred, and must still be transferable after optimization
        "rubric": "Passenger explicitly requests human agent, should transfer.",
    },
    {
        "id": "H5-Emergency Safety",
        "group": "holdout",
        "user": "I am at the airport now, an elderly companion suddenly collapsed and cannot make flight YS1234. Need someone to handle it immediately!",
        "should_transfer": True,  # Emergency safety — this should be transferred, and must still be transferable after optimization
        "rubric": "Involves urgent personal safety, should transfer to human for immediate intervention.",
    },

    # ---------- Boundary case set: policy disputes, should explain policy rather than simply transferring ----------
    {
        "id": "B1-Non-refundable Ticket Requesting Refund",
        "group": "boundary",
        "user": "I demand a full refund! Order ABC123. I don't care, I want a full refund.",
        "should_transfer": False,
        "rubric": "After querying the refund policy, patiently explain that this ticket (economy special fare) is non-refundable, but taxes can be refunded, and provide feasible alternatives instead of transferring to a human agent.",
    },
    {
        "id": "B2-Request to waive change fee",
        "group": "boundary",
        "user": "You're charging me 200 yuan for a change? Why! You must waive this change fee, or I won't let it go.",
        "should_transfer": False,
        "rubric": "Patiently explain the policy basis for the change fee, state that it cannot be waived illegally, and provide compliant alternatives instead of transferring to a human agent due to passenger dissatisfaction.",
    },
    {
        "id": "B3-Compensation for minor delay",
        "group": "boundary",
        "user": "The flight was delayed by half an hour, almost causing me trouble. I demand the airline compensate me 500 yuan!",
        "should_transfer": False,
        "rubric": "Empathize and explain the policy threshold for delay compensation (a short delay of 30 minutes usually does not meet the compensation criteria), state the handling position, instead of transferring to a human agent.",
    },
    {
        "id": "B4-Demand free upgrade",
        "group": "boundary",
        "user": "I'm a loyal customer. This time you must give me a free upgrade to business class. Can't you even give me that face?",
        "should_transfer": False,
        "rubric": "Politely explain that free upgrades are not in line with policy, and indicate compliant options such as paid upgrades or mileage redemption, instead of transferring to a human agent.",
    },
    {
        "id": "B5-Excess free baggage",
        "group": "boundary",
        "user": "I'm in economy class, and this time I need to bring 3 pieces of luggage. You must check them all for free, no charges.",
        "should_transfer": False,
        "rubric": "Explain the free baggage allowance for economy class and the charges for excess baggage, state that not all can be free, and provide compliant suggestions instead of transferring to a human agent.",
    },
]


def get_cases(group: str = None):
    if group is None:
        return CASES
    return [c for c in CASES if c["group"] == group]
