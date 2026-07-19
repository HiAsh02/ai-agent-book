"""
A multi-turn "Customer Service Refund Agent" task for cost analysis (corresponding to the customer service refund example in Book 6.x, Table 6-4).

To make the experiment reproducible and not rely on the randomness of model tool calls, we use a "controlled tool environment":
Each round, we feed the tool's return result from the previous step to the model, and the model (real LLM call) decides the next step.
The tool return content is preset (in a real API, it would be the return from the order system/logistics system),
but every LLM call, every token usage, and every cent of cost is real.

This file orthogonally separates the two switches "KV-cache friendly" and "compress context",
allowing a complete 2×2 A/B combination (corresponding to the book's comparison of enabling/disabling KV Cache and enabling/disabling context compression):
  run_scenario(kv_cache=False, compress=False) —— A naive (unstable prefix + no compression)
  run_scenario(kv_cache=True,  compress=False) —— KV-cache only (stable long prefix, history not compressed)
  run_scenario(kv_cache=False, compress=True)  —— Compression only (unstable prefix, old rounds summarized)
  run_scenario(kv_cache=True,  compress=True)  —— B optimized (stable prefix + compression, both levers combined)
Compatible with old interfaces: run_naive == (False, False), run_optimized == (True, True).
"""

import uuid
from functools import lru_cache

from config import MODEL, Pricing
from tracer import Tracer

#  Keep the complete tool returns for the last few rounds (compress earlier ones into a one-sentence summary). When compression is disabled, treat as infinite.
KEEP_VERBOSE = 2

#  Limit output length per round: This experiment focuses on the two levers of KV-cache and compression on the "input side",
#  keeping output tokens at a similar level to avoid random fluctuations in model generation length interfering with A/B cost comparison.
MAX_OUTPUT_TOKENS = 160

# ---------------------------------------------------------------------------
#  A "sufficiently long and stable" system prompt + tool definition (> 1024 tokens),
#  This is key for KV-cache hits: stable long prefixes are automatically cached by OpenAI.
#  The content is a realistic system specification and tool manual for a customer service refund agent.
# ---------------------------------------------------------------------------
STABLE_SYSTEM_PROMPT = """You are a senior customer service agent for "CloudBuy Mall", specializing in after-sales and refund matters. You must strictly follow the following work guidelines.

# Role and Goal
Your goal is to efficiently and politely help users complete after-sales requests such as refunds, returns, exchanges, and logistics inquiries while adhering to platform rules.
You should proactively clarify requests, verify order status, determine if refund policies apply, and execute operations within your authority.

# Available Tool Manual
1. query_order(order_id): Query order details. Returns fields: order_id, status, item_name, sku, price,
   quantity, pay_time, pay_channel, buyer_note, seller_note, is_prepaid, warehouse, promotion_tags.
2. query_logistics(order_id): Query logistics tracking. Returns fields: carrier, tracking_no, current_status,
   last_scan_time, last_scan_location, estimated_delivery, full_trace (array, each scan node).
3. check_refund_policy(sku, reason): Query refund policy for the given SKU and reason. Returns fields:
   refundable, need_return, restocking_fee_rate, refund_window_days, special_notes, approval_required.
4. query_user_history(user_id): Query user history for risk control. Returns: total_orders, refund_count_90d,
   dispute_count, risk_level, vip_tier, register_days.
5. issue_refund(order_id, amount, reason): Initiate a refund. Returns: refund_id, status, expected_arrival,
   channel, operator. Only callable when policy allows and amount does not exceed the actual paid amount.
6. send_notification(user_id, channel, template, params): Send notification to user (sms/app/email).

# Decision Guidelines
- First verify if the order exists and if its status allows refund (different paths for not shipped, shipped but not signed, signed within 7 days).
- Not shipped: Full refund directly, no return needed.
- Shipped but not signed: Intercept logistics or wait for return; refund initiated after return is signed.
- Signed within 7 days and no quality issue: 7-day no-reason return applies, may charge a restocking fee (restocking_fee_rate).
- Quality issue: Full refund with no restocking fee; user must provide evidence.
- Large refunds (> 500 yuan) or high-risk users (risk_level=high) require manual approval (approval_required=true).
- Each step should include a brief Chinese reasoning explaining "based on what information, decide which tool to call next or what conclusion to draw".

# Output Requirements
- Be professional, concise, and empathetic.
- Only advance one step per round; do not fabricate data not yet returned by tools.
- When resolved, clearly inform the user of the refund amount, expected arrival time, and next steps.

# Compliance and Risk Control
- Do not disclose other users' information; do not promise compensation beyond policy; amounts and policies are based on tool returns.
- Be cautious of suspected fraud (short-term high-frequency refunds, abnormal logistics) and trigger manual approval.
Always adhere to all the above guidelines."""


# ---------------------------------------------------------------------------
#  Preset multi-turn script: user request + tool returns for each step (in real API, from backend systems).
#  Tool returns are deliberately verbose (large JSON) to reflect the token cost of injecting tool results into context.
# ---------------------------------------------------------------------------
USER_REQUEST = (
    "Hello, I bought Bluetooth earphones last week (order number ORD20240517001). They arrived but I can't connect them."
    "I've tried various methods but nothing works. I want to return and refund. How should I proceed?"
)

#  Each round: (logical step name, associated tool, verbose return text of that tool)
#  Tool returns are written to be large (real order/logistics/knowledge base returns often hundreds to thousands of tokens),
#  to reflect the amplification factor of "tool results injected into context being repeatedly billed in subsequent rounds".
_LOGISTICS_TRACE = ",".join(
    '{"time":"2024-05-%02dT%02d:%02d","loc":"%s","desc":"%s","operator":"SF%04d","scan_type":"auto"}'
    % (17 + i // 6, 6 + i, (i * 7) % 60, loc, desc, 1000 + i)
    for i, (loc, desc) in enumerate([
        ("East China 1 Warehouse", "Package picked up, weight 0.42kg"), ("East China 1 Warehouse Sorting Center", "Sorted, dispatched to Shanghai Transfer"),
        ("Shanghai Transfer Center", "Arrived at transfer center"), ("Shanghai Transfer Center", "Dispatched, in transit"),
        ("Suzhou Transfer Station", "Transit via"), ("Shanghai Pudong Distribution Point", "Arrived at delivery station"),
        ("Shanghai Pudong Distribution Point", "Scheduled for delivery"), ("Pudong xx Business Point", "Delivering, contacting recipient"),
        ("Pudong xx Business Point", "First delivery attempt, no answer"), ("Pudong xx Business Point", "Second delivery"),
        ("Pudong xx Business Point", "Signed, recipient: self"),
    ])
)

TOOL_RESULTS = [
    ("turn-1", "query_order",
     '{"order_id":"ORD20240517001","status":"SIGNED","item_name":"Acme Active Noise Cancelling Bluetooth Earphones Pro",'
     '"sku":"SKU-BT-9981","price":499.00,"quantity":1,"pay_time":"2024-05-17T10:22:31",'
     '"pay_channel":"wechat_pay","buyer_note":"Hope to ship ASAP, it\'s a gift","seller_note":"Inventory checked",'
     '"is_prepaid":true,"warehouse":"East China Warehouse 1","promotion_tags":["Spend 300 get 30 off","Member Day","New Customer Gift"],'
     '"actual_paid":469.00,"coupon_used":"CPN-30","points_earned":469,"invoice_requested":false,'
     '"sign_time":"2024-05-19T14:03:11","after_sale_window_end":"2024-05-26T23:59:59",'
     '"sub_items":[{"sku":"SKU-BT-9981","name":"Earphone main unit","qty":1},{"sku":"SKU-BT-9981-CASE","name":"Charging case","qty":1},{"sku":"SKU-BT-9981-TIP","name":"Eartip set","qty":1}],'
     '"address_hash":"a1b2c3d4","channel":"app","device":"iOS","order_source":"Homepage recommendation"}'),
    ("turn-2", "query_logistics",
     '{"carrier":"SF Express","tracking_no":"SF1234567890123","current_status":"Signed",'
     '"last_scan_time":"2024-05-19T14:03:11","last_scan_location":"Pudong New Area, Shanghai xx Service Point",'
     '"estimated_delivery":"2024-05-19","weight_kg":0.42,"volume":"20x15x8cm","insured":true,'
     '"full_trace":[' + _LOGISTICS_TRACE + ']}'),
    ("turn-3", "check_refund_policy",
     '{"sku":"SKU-BT-9981","reason":"quality_issue_cannot_connect","refundable":true,'
     '"need_return":true,"restocking_fee_rate":0.0,"refund_window_days":7,'
     '"special_notes":"Refund for quality issues is free of handling fee; user needs to return the item and quality inspection confirms if it is a quality issue;'
     'if inspection determines it is not a quality issue (e.g., human damage, unauthorized repair), the item will be returned without refund;'
     'return shipping is covered by the platform, user needs to apply for an electronic shipping label in the system; refund will be initiated within 1 business day after quality inspection passes;'
     'for 3C electronics, items that have been activated or bound to an account must be unbinded before return, otherwise quality inspection will not pass.",'
     '"approval_required":false,"category":"3C-Electronics","quality_claim_supported":true,'
     '"return_label_provided":true,"qc_sla_days":2,"related_policy_ids":["P-3C-01","P-3C-07","P-QC-12"]}'),
    ("turn-4", "query_knowledge_base",
     '{"query":"Bluetooth earphones cannot connect troubleshooting","hits":['
     '{"kb_id":"KB-1001","title":"Common reasons for Bluetooth earphones not connecting","content":"1. Not in pairing mode;'
     '2. Phone Bluetooth cache anomaly, need to forget device and reconnect; 3. Firmware version too low; 4. Low battery; 5. Multiple devices competing for connection."},'
     '{"kb_id":"KB-1002","title":"Acme Pro series reset method","content":"Press and hold the charging case button for 15 seconds until the indicator flashes red and white alternately to complete reset,'
     'then delete the old pairing record on the phone and search again. If the device still cannot be found after reset, it is likely a hardware fault, suggest quality issue return/exchange."},'
     '{"kb_id":"KB-1003","title":"Quality issue determination criteria","content":"Reset ineffective + still cannot connect with another device + no liquid ingress or appearance damage,'
     'usually determined as a quality issue, supporting free return/exchange."}],"suggested_action":"Guide user to reset; if ineffective, determine as quality issue and proceed with refund process"}'),
    ("turn-5", "query_user_history",
     '{"user_id":"U-88123","total_orders":37,"refund_count_90d":1,"dispute_count":0,'
     '"risk_level":"low","vip_tier":"gold","register_days":1180,"payment_disputes":0,'
     '"avg_order_value":312.5,"last_refund_reason":"Wrong size","chargeback_count":0,'
     '"complaint_count":0,"account_status":"normal","fraud_flags":[],"lifetime_value":11562.5}'),
    ("turn-6", "issue_refund",
     '{"refund_id":"RF20240520777","status":"APPROVED","amount":469.00,'
     '"expected_arrival":"1-3 business days","channel":"Original payment method refund-WeChat","operator":"agent-bot",'
     '"return_shipping":"Platform covers","return_address":"East China Warehouse 1 Returns Team","return_label":"SF-RET-998877",'
     '"qc_required":true,"qc_deadline":"2024-05-27","refund_flow":"pending_return->qc->refund"}'),
    ("turn-7", "send_notification",
     '{"user_id":"U-88123","channel":"app","template":"refund_approved",'
     '"delivered":true,"message_id":"MSG-556677","sent_time":"2024-05-20T15:20:03",'
     '"params":{"refund_id":"RF20240520777","amount":469.00,"return_label":"SF-RET-998877"},'
     '"read_receipt":false,"fallback_sms_scheduled":true}'),
    ("turn-8", "close_ticket",
     '{"ticket_id":"TK-20240520-3345","status":"resolved","resolution":"refund_after_return",'
     '"csat_survey_sent":true,"handle_time_s":184,"escalated":false,"agent":"agent-bot",'
     '"summary_logged":true,"tags":["Refund","Quality Issue","3C","Closed"]}'),
]

#  One-sentence summary of previous rounds for "context compression" strategy (compress verbose tool returns into key points)
TOOL_SUMMARIES = {
    "turn-1": "[Summary] Order ORD20240517001: Acme Noise Cancelling Earphones Pro, paid 469 yuan, signed on 5/19, after-sales window until 5/26.",
    "turn-2": "[Summary] Logistics: SF Express signed (5/19 14:03, signed by self), 11 tracking nodes all normal without anomalies.",
    "turn-3": "[Summary] Refund policy: Quality issues can be returned, no handling fee, need to return for inspection, return shipping covered by platform, no manual approval required.",
    "turn-4": "[Summary] Knowledge base: First guide user to reset earphones; if reset ineffective, determine as quality issue, support free return/exchange.",
    "turn-5": "[Summary] User risk control: 37 orders/90 days with only 1 refund/low risk/gold member, good reputation, no fraud markers.",
    "turn-6": "[Summary] Refund RF20240520777 has been initiated: 469 yuan refunded to WeChat via original route, requires return for quality inspection, platform covers return shipping.",
    "turn-7": "[Summary] User has been notified via app that the refund is approved, with return shipping label attached.",
}


def _next_user_msg(tool_name: str, tool_result: str) -> str:
    """Wrap the tool return result into the next user message fed to the model."""
    return (
        f"[Tool {tool_name} Return Result]\n{tool_result}\n\n"
        f"Based on the above results, provide your reasoning and decide the next action."
    )


@lru_cache(maxsize=1)
def _encoder():
    """Use the current model's tiktoken encoder (available offline) to estimate the tokens for 'tool return injection'."""
    import tiktoken
    try:
        return tiktoken.encoding_for_model(MODEL)
    except Exception:
        return tiktoken.get_encoding("cl100k_base")


def _ntok(text: str) -> int:
    return len(_encoder().encode(text))


# ---------------------------------------------------------------------------
#  Registration table for four A/B scenarios: name + two switches.
# ---------------------------------------------------------------------------
SCENARIOS = {
    "naive":    ("A Naive (no cache / no compression)", False, False),
    "kv":       ("KV Only Cache (stable prefix / no compression)", True, False),
    "compress": ("Only Compression (unstable prefix / summary)", False, True),
    "both":     ("B Optimized (KV cache + compression)", True, True),
}


def build_messages(idx, step, tool, result, turns, kv_cache, compress):
    """Construct the messages to be sent to the model for the idx-th round, and return the cumulative tokens of 'tool return injection' in the current round's input.

    kv_cache=True → system uses a byte-stable long prefix (can be auto-cached by OpenAI);
    kv_cache=False → prepend a random session header at the very beginning of system each round, breaking prefix consistency.
    compress=True → only the most recent KEEP_VERBOSE rounds retain full tool returns; earlier rounds are compressed into a one-sentence summary.
    """
    if kv_cache:
        system = {"role": "system", "content": STABLE_SYSTEM_PROMPT}
    else:
        volatile_head = f"[Session Tracking] session={uuid.uuid4()} Request Number={uuid.uuid4()}\n\n"
        system = {"role": "system", "content": volatile_head + STABLE_SYSTEM_PROMPT}

    history = [{"role": "user", "content": USER_REQUEST}]
    tool_ctx_tokens = 0
    for j, (p_step, p_assistant, p_tool, p_result) in enumerate(turns):
        history.append({"role": "assistant", "content": p_assistant})
        if compress and idx - j > KEEP_VERBOSE:
            compact = TOOL_SUMMARIES.get(p_step, f"[Summary] {p_tool} Completed.")
            history.append({"role": "user", "content": compact})
            tool_ctx_tokens += _ntok(compact)
        else:
            history.append({"role": "user", "content": _next_user_msg(p_tool, p_result)})
            tool_ctx_tokens += _ntok(p_result)

    messages = [system] + history + [
        {"role": "user", "content": _next_user_msg(tool, result)}
    ]
    tool_ctx_tokens += _ntok(result)   # Newly injected tool returns for this round
    return messages, tool_ctx_tokens


def run_scenario(client, kv_cache: bool, compress: bool, name: str = None,
                 pricing: Pricing = None) -> Tracer:
    """Run an 8-round customer service refund task, with two switches orthogonally combined to form one cell in a 2×2 grid.

    Both groups perform the same logical work, differing only in context construction, so the cost difference comes purely from
    the two input-side levers: KV-cache reuse and context compression.
    """
    tracer = Tracer(client, name=name or f"kv={kv_cache},compress={compress}",
                    pricing=pricing)
    turns = []
    for idx, (step, tool, result) in enumerate(TOOL_RESULTS):
        messages, tool_ctx = build_messages(
            idx, step, tool, result, turns, kv_cache, compress)
        resp = tracer.chat(step=step, tool=tool, tool_ctx_tokens=tool_ctx,
                           model=MODEL, messages=messages, temperature=0,
                           max_tokens=MAX_OUTPUT_TOKENS)
        assistant_text = resp.choices[0].message.content or ""
        turns.append((step, assistant_text, tool, result))
    return tracer


def run_naive(client, pricing: Pricing = None) -> Tracer:
    """(a) Naive approach: unstable prefix + no history compression (KV-cache misses, context grows unbounded)."""
    return run_scenario(client, kv_cache=False, compress=False,
                        name=SCENARIOS["naive"][0], pricing=pricing)


def run_optimized(client, pricing: Pricing = None) -> Tracer:
    """(b) KV-cache friendly + context compression: stable long prefix hits cache + old rounds summarized."""
    return run_scenario(client, kv_cache=True, compress=True,
                        name=SCENARIOS["both"][0], pricing=pricing)
