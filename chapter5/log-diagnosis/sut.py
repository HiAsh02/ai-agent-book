"""
sut.py —— System Under Test (Deterministic Simulation of the System Under Test)

The core of regression testing is "replay with the same input, assert that the fixed system produces correct behavior."
Here, a **deterministic** simulator is used to emulate the online Agent system:

- run_task(task_input, fixed=False): Reproduces the online (buggy) behavior,
  producing trajectories that contain the same three known issues as the production trajectories.
- run_task(task_input, fixed=True): Simulates the "fixed" system,
  correctly executing pre-validation / retry backoff / inventory degradation.

replay.py replays the same input with fixed=False / fixed=True respectively,
thus demonstrating the "fail (reproduce bug)" and "pass (verify fix)" of the same regression test case.

The trajectory structure is identical to data/trajectories.jsonl for easy comparison.
"""

from typing import Dict, Any


def run_task(task_input: Dict[str, Any], fixed: bool = False) -> Dict[str, Any]:
    """Given a task input, deterministically run the system under test and return a trajectory."""
    intent = task_input.get("intent")
    order_id = task_input.get("order_id", "UNKNOWN")
    turns = []
    idx = 0

    def add(**kw):
        nonlocal idx
        kw["index"] = idx
        idx += 1
        turns.append(kw)

    # 0. User Input & Intent Recognition
    add(role="user", content=f"task={intent}, order={order_id}")
    add(role="assistant", module="intent_parser", content=f"Intent={intent}")

    final_status = "success"

    if intent == "refund":
        # Query Order
        add(role="tool", module="order_service", tool="query_order",
            input={"order_id": order_id},
            output={"status": task_input.get("order_status", "paid")},
            status="success", latency_ms=210)

        # R1: Refund Pre-qualification Check (executed only in fixed version)
        if fixed:
            add(role="tool", module="order_service", tool="verify_refund_eligibility",
                input={"order_id": order_id},
                output={"eligible": True}, status="success", latency_ms=120)

        # R2: Payment Retry + Backoff
        if task_input.get("payment_flaky") and not fixed:
            # Online bug: No backoff, false success after consecutive failures
            for _ in range(3):
                add(role="tool", module="payment_service", tool="process_refund",
                    input={"order_id": order_id},
                    output={"error": "gateway_timeout"},
                    status="error", latency_ms=3000)
            add(role="assistant", module="payment_service",
                content="Multiple failures, still ends as success (bug)")
            final_status = "success"  # False success
        elif task_input.get("payment_flaky") and fixed:
            # Fix: Retry with backoff after one failure succeeds
            add(role="tool", module="payment_service", tool="process_refund",
                input={"order_id": order_id},
                output={"error": "gateway_timeout"}, status="error", latency_ms=1500)
            add(role="assistant", module="payment_service", content="Retry after 800ms backoff")
            add(role="tool", module="payment_service", tool="process_refund",
                input={"order_id": order_id, "retry": 1},
                output={"refund_id": "R-OK"}, status="success", latency_ms=600)
        else:
            add(role="tool", module="payment_service", tool="process_refund",
                input={"order_id": order_id},
                output={"refund_id": "R-OK"}, status="success", latency_ms=540)

    elif intent == "order_status":
        add(role="tool", module="order_service", tool="query_order",
            input={"order_id": order_id},
            output={"status": "paid", "sku": task_input.get("sku")},
            status="success", latency_ms=220)

        # R3: Inventory Query Latency
        if task_input.get("slow_inventory") and not fixed:
            # Online bug: Timeout still blocks waiting, no degradation
            add(role="tool", module="inventory_service", tool="check_stock",
                input={"sku": task_input.get("sku")},
                output={"stock": 12}, status="success", latency_ms=8300)
        elif task_input.get("slow_inventory") and fixed:
            # Fix: Exceeds threshold, takes degradation path, returns quickly
            add(role="tool", module="inventory_service", tool="check_stock",
                input={"sku": task_input.get("sku"), "degraded": True},
                output={"stock": "cached:12", "degraded": True},
                status="success", latency_ms=400)
        else:
            add(role="tool", module="inventory_service", tool="check_stock",
                input={"sku": task_input.get("sku")},
                output={"stock": 5}, status="success", latency_ms=300)

    # R4: Notify User
    add(role="tool", module="notification_service", tool="notify_user",
        input={"final_status": final_status},
        output={"sent": True}, status="success", latency_ms=60)

    return {
        "trajectory_id": f"REPLAY::{order_id}::{'fixed' if fixed else 'buggy'}",
        "task_input": task_input,
        "final_status": final_status,
        "turns": turns,
    }
