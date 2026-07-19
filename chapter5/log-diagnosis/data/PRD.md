# Product Requirements Document (PRD, Abridged) — Order Refund Agent

## R1 Refund Compliance Check (P0)
Before initiating any refund (`process_refund`), **must** first call `verify_refund_eligibility` to complete the refund eligibility check.
Proceeding with a refund without this check poses a serious compliance/financial risk and is prohibited.

## R2 Payment Retry and Reporting (P0)
`process_refund` calls the third-party payment gateway. When the gateway occasionally fails, the system should retry with backoff;
if it still fails after all retries, the task must be marked as `failed` and the user must be notified. **Do not** silently end or falsely report success after multiple failures.

## R3 Inventory Query Latency (P1)
The single-call latency of `check_stock` must be less than **5000ms**. If the threshold is exceeded, a degradation should be triggered (return cached data or an "inventory query busy" prompt), and the user must not be kept waiting for a long time.

## R4 Result Notification (P2)
When a task ends (whether successful or failed), the final result must be notified to the user via `notification_service.notify_user`.
