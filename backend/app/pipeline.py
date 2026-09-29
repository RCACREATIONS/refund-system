from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.ai.client import LLMClient
from app.models import Claim, PolicyContext, PolicyResult, RefundRequest
from app.policy.engine import evaluate
from app.repository import InMemoryRepository
from app.security.guards import contains_canary, normalize_message


def template_reply(outcome: str, amount: Decimal) -> str:
    if outcome == "approved":
        return f"Your refund is approved for ${amount:.2f}. We’ll send it back to your original payment method."
    if outcome == "denied":
        return "We couldn’t approve this refund under the current return policy. A support specialist can help if you have more context."
    return "We’ve passed this request to a support specialist for review. You’ll see an update here when it is resolved."


def receipt_for(result: PolicyResult, context: PolicyContext, outcome: str) -> dict:
    checks = [
        {"label": "Order found on your account", "passed": context.order is not None},
        {"label": "Within return window", "passed": any(hit.rule_id == "R2" and hit.effect == "pass" for hit in result.rule_hits)},
        {"label": "Item eligible", "passed": bool(result.eligible_skus)},
        {"label": "Within instant-approval limit", "passed": not any(hit.rule_id == "R3" for hit in result.rule_hits)},
    ]
    next_step = (
        "Refund will be sent to your original payment method."
        if outcome == "approved"
        else "You can ask a support specialist to review this decision."
        if outcome in {"denied", "escalated"}
        else "No action is needed yet."
    )
    return {"outcome": outcome, "amount": str(result.refund_amount if outcome == "approved" else Decimal("0.00")), "checks": checks, "next_step": next_step}


class RefundPipeline:
    def __init__(self, repo: InMemoryRepository, client: LLMClient) -> None:
        self.repo = repo
        self.client = client

    async def process(self, customer_id: int, message: str, source: str = "user", created_at: datetime | None = None) -> dict:
        customer = self.repo.customer(customer_id)
        if not customer:
            raise ValueError("Unknown customer")
        normalized = normalize_message(message)
        screen_task = self.client.screen(normalized)
        extraction_task = self.client.extract(normalized)
        screen, claim = await asyncio.gather(screen_task, extraction_task)
        if claim.needs_clarification:
            return {"needs_clarification": True, "question": claim.clarification_question}

        order = self.repo.order_for_customer(claim.order_id, customer_id)
        raw_order = self.repo.raw_order(claim.order_id)
        flags = [item["category"] for item in screen.get("evidence", [])] if screen.get("suspected") else []
        if raw_order and not order:
            flags.append("foreign_order")
        context = PolicyContext(
            customer_id=customer_id,
            claim=claim,
            order=order,
            order_age_days=(datetime.now(timezone.utc).date() - order.delivered_at).days if order else None,
            recent_refund_count=self.repo.recent_refund_count(customer_id),
            flags=flags,
        )
        result = evaluate(context)
        review = await self.client.review(normalized, claim, result)
        engine_outcome = result.outcome
        final_outcome = engine_outcome
        driver = "policy_engine"
        if engine_outcome == "approved" and review.get("recommendation") == "escalate":
            final_outcome = "escalated"
            driver = "ai_review"
        if final_outcome == "denied":
            driver = "policy_engine"
        amount = result.refund_amount if final_outcome == "approved" else result.refund_amount
        reply_data = await self.client.reply(final_outcome, amount, result)
        reply = str(reply_data.get("reply", ""))
        firewall_reasons = []
        if reply_data.get("stated_outcome") != final_outcome:
            firewall_reasons.append("stated_outcome_mismatch")
        if contains_canary(reply):
            firewall_reasons.append("canary_leak")
        lowered = reply.lower()
        if any(word in lowered for word in ("prompt", "system", "instruction", "injection", "flagged")):
            firewall_reasons.append("internal_language")
        if final_outcome != "approved" and "$" in reply:
            firewall_reasons.append("amount_on_nonapproval")
        if final_outcome == "approved" and f"${amount:.2f}" not in reply:
            firewall_reasons.append("amount_missing")
        if not reply or len(reply) > 1000:
            firewall_reasons.append("reply_length")
        if firewall_reasons:
            reply = template_reply(final_outcome, amount)

        now = created_at or datetime.now(timezone.utc)
        request = RefundRequest(
            id=0,
            customer_id=customer_id,
            order_id=claim.order_id,
            message=normalized,
            outcome=final_outcome,
            refund_amount=amount,
            customer_reply=reply,
            review_status="pending_review" if final_outcome == "escalated" else "auto",
            source=source if source in {"user", "seed", "redteam"} else "user",
            created_at=now,
            receipt=receipt_for(result, context, final_outcome),
            claim=claim,
            policy_input=context,
            policy_result=result,
        )
        request = self.repo.create_request(request)
        self.repo.add_audit(request.id, "input_screen", screen)
        self.repo.add_audit(request.id, "extraction", claim.model_dump(mode="json"))
        self.repo.add_audit(
            request.id,
            "context",
            {"customer_id": customer_id, "order_found": bool(order), "recent_refund_count": context.recent_refund_count},
        )
        self.repo.add_audit(request.id, "policy_input", context.model_dump(mode="json"))
        self.repo.add_audit(request.id, "policy", result.model_dump(mode="json"))
        self.repo.add_audit(request.id, "ai_review", review)
        self.repo.add_audit(request.id, "reconcile", {"engine_outcome": engine_outcome, "final_outcome": final_outcome, "driver": driver})
        if firewall_reasons:
            self.repo.add_audit(request.id, "reply_firewall_triggered", {"reasons": firewall_reasons})
        self.repo.add_audit(request.id, "reply", {"reply": reply, "stated_outcome": final_outcome})
        self.repo.add_audit(request.id, "persist", {"review_status": request.review_status})
        return {"request_id": request.id, "outcome": final_outcome, "reply": reply, "receipt": request.receipt}
