from __future__ import annotations

import base64
import re
import secrets
import unicodedata


CANARY = secrets.token_hex(12)

INJECTION_PATTERNS: list[tuple[str, str]] = [
    ("instruction_override", r"\bignore\s+(all|any|the)\s+(previous|prior|above)\s+instructions?\b"),
    ("role_switch", r"\b(you are now|admin mode|developer mode|dan mode|system mode)\b"),
    ("prompt_exfiltration", r"\b(reveal|show|print|tell me).{0,30}\b(system prompt|instructions|threshold|rules)\b"),
    ("fake_role_marker", r"(?i)(<\s*(system|assistant)\s*>|\[\s*(system|assistant)\s*\])"),
    ("no_logging", r"\b(do not|don't|never)\s+(log|record|audit)\b"),
    ("authority_claim", r"\b(my lawyer|manager approved|legal authority|ceo said)\b"),
    ("outcome_json", r'\{\s*["\']outcome["\']\s*:\s*["\']approved["\']'),
    ("encoded_payload", r"\b(?:[A-Za-z0-9+/]{32,}={0,2}|[0-9a-f]{24,})\b"),
]


def normalize_message(message: str, limit: int = 1500) -> str:
    cleaned = "".join(ch for ch in unicodedata.normalize("NFKC", message) if ch.isprintable() or ch in "\n\t")
    cleaned = cleaned.replace("</customer_message>", "<\\/customer_message>")
    return " ".join(cleaned.split())[:limit]


def screen_message(message: str) -> dict:
    normalized = normalize_message(message)
    matches: list[dict[str, str]] = []
    for category, pattern in INJECTION_PATTERNS:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if match:
            matches.append({"category": category, "evidence": match.group(0)[:80]})
    try:
        decoded = base64.b64decode(normalized, validate=True).decode("utf-8", errors="ignore")
        if "ignore" in decoded.lower() or "system" in decoded.lower():
            matches.append({"category": "encoded_payload", "evidence": "decoded instruction-like payload"})
    except Exception:
        pass
    return {
        "suspected": bool(matches),
        "confidence": min(0.99, 0.65 + 0.08 * len(matches)) if matches else 0.02,
        "category": matches[0]["category"] if matches else "none",
        "evidence": matches,
    }


def safe_prompt(text: str) -> str:
    return f"<customer_message>{normalize_message(text)}</customer_message>"


def contains_canary(value: str) -> bool:
    return CANARY.lower() in value.lower()
