from __future__ import annotations

from decimal import Decimal

from app.models import PolicyContext, PolicyParams, PolicyResult, RuleHit


def evaluate(ctx: PolicyContext, params: PolicyParams | None = None) -> PolicyResult:
    """Evaluate a claim using deterministic, side-effect-free policy rules."""
    params = PolicyParams.model_validate(params or PolicyParams())
    hits: list[RuleHit] = []
    order = ctx.order

    if order is None:
        hits.append(RuleHit(rule_id="R5", effect="deny", detail="Order is not owned by this customer."))
        for flag in ctx.flags:
            hits.append(RuleHit(rule_id="R7", effect="info", detail=f"Safety flag recorded: {flag}"))
        return PolicyResult(outcome="denied", rule_hits=hits)

    selected = order.items
    if ctx.claim.skus:
        selected = [item for item in order.items if item.sku in ctx.claim.skus]
        unknown = [sku for sku in ctx.claim.skus if sku not in {item.sku for item in order.items}]
        if unknown:
            hits.append(RuleHit(rule_id="R7", effect="escalate", detail="Claim references an item not on the order."))
            return PolicyResult(outcome="escalated", rule_hits=hits)

    eligible = [item for item in selected if not item.final_sale]
    excluded = [item for item in selected if item.final_sale]
    if excluded:
        hits.append(
            RuleHit(
                rule_id="R1",
                effect="info",
                detail=f"{len(excluded)} final-sale item(s) excluded from assessment.",
            )
        )
    if not eligible:
        hits.append(RuleHit(rule_id="R1", effect="deny", detail="All claimed items are final sale."))
        for flag in ctx.flags:
            hits.append(RuleHit(rule_id="R7", effect="info", detail=f"Safety flag recorded: {flag}"))
        return PolicyResult(outcome="denied", rule_hits=hits)

    age = ctx.order_age_days
    if age is None:
        age = (ctx.today - order.delivered_at).days
    if age > params.window_days:
        hits.append(RuleHit(rule_id="R2", effect="deny", detail=f"Delivery was {age} days ago."))
        for flag in ctx.flags:
            hits.append(RuleHit(rule_id="R7", effect="info", detail=f"Safety flag recorded: {flag}"))
        return PolicyResult(outcome="denied", rule_hits=hits)
    hits.append(RuleHit(rule_id="R2", effect="pass", detail=f"Within the {params.window_days}-day return window."))

    amount = sum((item.price for item in eligible), Decimal("0.00")).quantize(Decimal("0.01"))
    if ctx.claim.requested_amount is not None and ctx.claim.requested_amount > order.total:
        hits.append(RuleHit(rule_id="R7", effect="escalate", detail="Requested amount exceeds order total."))
    if ctx.flags:
        for flag in ctx.flags:
            hits.append(RuleHit(rule_id="R7", effect="escalate", detail=f"Suspicious request: {flag}"))
    if ctx.recent_refund_count >= params.repeat_limit:
        hits.append(
            RuleHit(
                rule_id="R6",
                effect="escalate",
                detail=f"{ctx.recent_refund_count} refunds in the last {params.repeat_window_days} days.",
            )
        )
    if amount > params.review_threshold:
        hits.append(
            RuleHit(
                rule_id="R3",
                effect="escalate",
                detail=f"Eligible amount ${amount:.2f} is above the review threshold.",
            )
        )

    if any(hit.effect == "escalate" for hit in hits):
        outcome = "escalated"
    else:
        if ctx.claim.reason in {"damaged", "wrong_item", "not_as_described"}:
            hits.append(RuleHit(rule_id="R4", effect="approve", detail="Item issue is eligible for approval."))
        elif ctx.claim.reason == "changed_mind":
            hits.append(RuleHit(rule_id="R8", effect="approve", detail="Non-final-sale change-of-mind return is eligible."))
        else:
            hits.append(RuleHit(rule_id="R7", effect="escalate", detail="The request reason is unclear."))
        outcome = "approved" if hits[-1].effect == "approve" else "escalated"

    return PolicyResult(
        outcome=outcome,
        refund_amount=amount if outcome in {"approved", "escalated"} else Decimal("0.00"),
        rule_hits=hits,
        eligible_skus=[item.sku for item in eligible],
    )
