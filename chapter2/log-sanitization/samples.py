"""
Representative samples for log desensitization demonstration

These samples simulate the most common scenarios where sensitive information is leaked during real Agent runtime:
HTTP request/response of tool calls, customer service conversations, database connection errors, CI/Git logs,
and configuration dumps. They mix key-type (API Key, token, private key) and PII-type
(ID card, phone number, credit card, email) sensitive information, making it easy to demonstrate the coverage of desensitization.

Note: All keys, card numbers, and ID numbers below are fictitious and used only for demonstration, not corresponding to any real accounts.
"""

SAMPLES = [
    (
        "Tool Call Log (HTTP Request/Response)",
        """[2024-05-12 09:14:22] TOOL_CALL http_request
  url: https://api.example.com/v1/users/8842
  headers: {"Authorization": "Bearer sk-proj-ABCD1234efgh5678IJKL9012mnop3456qrst", "X-Api-Key": "AIzaSyD-EXAMPLEfakeKEY1234567890abcdef12"}
  response: {"user_id": 8842, "email": "alice.wang@example.com", "phone": "13912345678"}""",
    ),
    (
        "Customer Service Conversation (PII Leakage)",
        """USER: Hello, I need to process reimbursement. My ID number is 11010119900307721X, and my phone number is 13800138000.
ASSISTANT: Okay, please also provide your bank card number for verification.
USER: The card number is 4111 1111 1111 1111, and my US Social Security number is 123-45-6789.
ASSISTANT: Received, I will register it for you now.""",
    ),
    (
        "Database Connection Error (Credential Leakage)",
        """[ERROR] db.connect failed after 3 retries
  dsn: postgres://admin:S3cr3t_P4ssw0rd@db.internal:5432/prod
  fallback_config: {"db_password": "hunter2xyz", "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE"}
  host_ip: 192.168.10.24""",
    ),
    (
        "CI / Git Log (Token Leakage)",
        """Cloning into 'service-repo'...
  remote: using deploy token ghp_16C7e42F292c6912E7710c838347Ae178B4a99
  Slack notify webhook token: xoxb-PLACEHOLDERfaketoken000000notarealslacktoken
  session jwt=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c""",
    ),
    (
        "Configuration Dump (Private Key Leakage)",
        """[DEBUG] dumping runtime config
  service_account_key: |
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA7QwZbq3vX9kLmN0pQrStUvWxYz1234567890abcdefghijkl
mnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0987654321zyxwvutsrqponm
QIDAQAB
-----END RSA PRIVATE KEY-----
  admin_contact: ops-team@example.com""",
    ),
]
