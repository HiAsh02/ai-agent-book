"""
Rule-based (regex) offline log desensitization engine

Complementary to the local LLM approach in agent.py: this module requires no model or network,
purely relies on regular expressions + validation algorithms (Luhn, ID checksum) to identify
sensitive information in logs / tool outputs. Fast, deterministic, suitable as the first line of defense before Agent logs are persisted.

Covered sensitive information categories (in descending match priority):
  - Private keys / certificates (PEM blocks)
  - JWT
  - Cloud vendor and third-party keys (AWS AKIA, GitHub, Slack, Google, OpenAI style sk-)
  - HTTP Authorization: Bearer tokens
  - Passwords / secret assignments in config (password=..., token: ... etc.)
  - Email addresses
  - Credit card numbers (Luhn check)
  - IBAN international bank account numbers
  - US Social Security Numbers (SSN)
  - Mainland China ID numbers (checksum validation)
  - Mainland China mobile phone numbers
  - IPv4 addresses

Each category is replaced with a category-tagged placeholder (e.g., [REDACTED_API_KEY]),
which both hides the original value and preserves readability of "what was here" for troubleshooting.
"""

import re
from collections import Counter
from typing import Dict, List, Tuple


def _luhn_ok(number: str) -> bool:
    """Luhn check, used to reduce false positives for credit card numbers"""
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _cn_id_ok(value: str) -> bool:
    """Mainland China second-generation ID number (18-digit) checksum validation"""
    s = value.upper()
    if len(s) != 18 or not s[:17].isdigit():
        return False
    weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    check_codes = "10X98765432"
    total = sum(int(s[i]) * weights[i] for i in range(17))
    return check_codes[total % 11] == s[17]


#  Each rule: (category, placeholder, compiled regex, capture group index for value, optional validation function)
#  Group index 0 means the entire match is redacted; N means only the Nth capture group is redacted (preserving key names and other context).
_RULES = [
    (
        "private_key", "[REDACTED_PRIVATE_KEY]",
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
            r"[\s\S]*?-----END (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"
        ),
        0, None,
    ),
    (
        "jwt", "[REDACTED_JWT]",
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
        0, None,
    ),
    (
        #  Password in connection string, e.g., postgres://user:PASSWORD@host:5432/db
        "url_credential", "[REDACTED_URL_CRED]",
        re.compile(r"://[^\s:/@]+:([^\s:/@]+)@"),
        1, None,
    ),
    (
        "aws_access_key", "[REDACTED_AWS_KEY]",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        0, None,
    ),
    (
        "github_token", "[REDACTED_GITHUB_TOKEN]",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        0, None,
    ),
    (
        "slack_token", "[REDACTED_SLACK_TOKEN]",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        0, None,
    ),
    (
        "google_api_key", "[REDACTED_GOOGLE_API_KEY]",
        re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
        0, None,
    ),
    (
        "api_key", "[REDACTED_API_KEY]",
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        0, None,
    ),
    (
        "bearer_token", "[REDACTED_BEARER_TOKEN]",
        re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._~+/=-]{10,})"),
        1, None,
    ),
    (
        "secret_assignment", "[REDACTED_SECRET]",
        re.compile(
            r"(?i)(?:password|passwd|pwd|secret|token|api[_-]?key|"
            r"access[_-]?key|auth|credential)[\"']?\s*[=:]\s*[\"']?([^\s\"',}]{4,})"
        ),
        1, None,
    ),
    (
        "email", "[REDACTED_EMAIL]",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        0, None,
    ),
    (
        "credit_card", "[REDACTED_CREDIT_CARD]",
        re.compile(r"\b(?:\d[ -]?){13,19}\b"),
        0, _luhn_ok,
    ),
    (
        "iban", "[REDACTED_IBAN]",
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
        0, None,
    ),
    (
        "us_ssn", "[REDACTED_SSN]",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        0, None,
    ),
    (
        "cn_id_card", "[REDACTED_ID_CARD]",
        re.compile(r"\b\d{17}[\dXx]\b"),
        0, _cn_id_ok,
    ),
    (
        "cn_phone", "[REDACTED_PHONE]",
        re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
        0, None,
    ),
    (
        "ip_address", "[REDACTED_IP]",
        re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
        0, None,
    ),
]

#  Human-readable Chinese category name, used for printing summary
CATEGORY_LABELS = {
    "private_key": "Private key / certificate",
    "jwt": "JWT token",
    "url_credential": "Connection string credential",
    "aws_access_key": "AWS access key",
    "github_token": "GitHub token",
    "slack_token": "Slack token",
    "google_api_key": "Google API Key",
    "api_key": "API Key (sk-)",
    "bearer_token": "Bearer token",
    "secret_assignment": "Password / secret assignment",
    "email": "Email address",
    "credit_card": "Credit card number",
    "iban": "IBAN bank account number",
    "us_ssn": "US Social Security Number (SSN)",
    "cn_id_card": "ID number",
    "cn_phone": "Mobile phone number",
    "ip_address": "IP address",
}


def sanitize(text: str) -> Tuple[str, List[Dict]]:
    """
    Apply offline rule-based desensitization to the text.

    Returns:
        - Desensitized text
        - List of hits, each item is {category, value, placeholder, start, end}
    """
    candidates: List[Dict] = []
    for priority, (category, placeholder, pattern, group, validator) in enumerate(_RULES):
        for m in pattern.finditer(text):
            start, end = m.span(group)
            if start < 0:  #  This capture group did not participate in the current match
                continue
            value = text[start:end]
            if validator and not validator(value):
                continue
            candidates.append({
                "category": category,
                "placeholder": placeholder,
                "value": value,
                "start": start,
                "end": end,
                "priority": priority,
            })

    #  Handle overlaps: higher priority (smaller number) rules win, avoiding duplicate/incorrect redaction of the same segment
    candidates.sort(key=lambda c: (c["priority"], c["start"]))
    accepted: List[Dict] = []
    for c in candidates:
        if any(not (c["end"] <= a["start"] or c["start"] >= a["end"]) for a in accepted):
            continue
        accepted.append(c)

    #  Rebuild desensitized text in positional order
    accepted.sort(key=lambda c: c["start"])
    parts: List[str] = []
    last = 0
    for c in accepted:
        parts.append(text[last:c["start"]])
        parts.append(c["placeholder"])
        last = c["end"]
    parts.append(text[last:])

    findings = [
        {k: c[k] for k in ("category", "value", "placeholder", "start", "end")}
        for c in accepted
    ]
    return "".join(parts), findings


def summarize(findings: List[Dict]) -> Counter:
    """Count hits per category"""
    return Counter(f["category"] for f in findings)


def print_report(name: str, original: str, redacted: str, findings: List[Dict]) -> None:
    """Print before/after and hit details for a single sample"""
    print(f"\n{'=' * 64}")
    print(f"Sample: {name}  (hit {len(findings)} sensitive information)")
    print("=" * 64)
    print("--- BEFORE ---")
    print(original.rstrip())
    print("\n--- AFTER ---")
    print(redacted.rstrip())
    if findings:
        print("\n--- Hit Details ---")
        for f in findings:
            label = CATEGORY_LABELS.get(f["category"], f["category"])
            print(f"   [{label}] {f['value']}  ->  {f['placeholder']}")


if __name__ == "__main__":
    # When running this module directly, perform a quick demo on built-in samples
    from samples import SAMPLES

    total = Counter()
    for name, text in SAMPLES:
        redacted, findings = sanitize(text)
        print_report(name, text, redacted, findings)
        total.update(summarize(findings))

    print(f"\n{'=' * 64}")
    print("Desensitization Category Summary")
    print("=" * 64)
    for category, count in total.most_common():
        label = CATEGORY_LABELS.get(category, category)
        print(f"   {label:<16} {count} items")
    print(f"\n   Total desensitized {sum(total.values())} sensitive information")
