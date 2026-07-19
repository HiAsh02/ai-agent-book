# Order Refund Agent System Architecture

This system is a multi-module Agent for e-commerce customer service scenarios, responsible for handling user order inquiries and refund requests.

## Module Breakdown

- **intent_parser (Intent Recognition)**: Parses user natural language, determines intent (`refund` / `order_status` / `chitchat`), and extracts entities such as order IDs.
- **order_service (Order Service)**: Handles order-related reads and writes.
  - Tool `query_order(order_id)`: Queries order status and amount.
  - Tool `verify_refund_eligibility(order_id)`: Checks whether the order meets refund conditions (whether payment has been made, whether it is within the refund time limit, whether a refund has already been processed). **This step is a mandatory prerequisite check in the refund flow.**
- **payment_service (Payment Service)**: Interfaces with third-party payment gateways.
  - Tool `process_refund(order_id, amount)`: Initiates a refund. The third-party gateway is occasionally unstable, requiring implementation of **retry + backoff** and reporting upon final failure; silent discarding is not allowed.
- **inventory_service (Inventory Service)**: Queries and restores inventory.
  - Tool `check_stock(sku)`: Queries stock. **Single call latency must not exceed 5000ms**; timeouts should follow a degradation path rather than blocking the main flow.
- **notification_service (Notification Service)**: Sends result notifications to users.

## Key Call Chain (Refund)

```
user -> intent_parser -> order_service.query_order
      -> order_service.verify_refund_eligibility   # Mandatory prerequisite check
      -> payment_service.process_refund            # Requires retry + backoff
      -> notification_service.notify_user
```

## Observability

The system logs one trajectory per task, recording the module, tool, input/output, status, and latency (latency_ms) for each interaction turn. Trajectories are used for online issue diagnosis and regression test replay.
