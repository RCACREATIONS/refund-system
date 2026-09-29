from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


Outcome = Literal["approved", "denied", "escalated"]
Reason = Literal["damaged", "wrong_item", "not_as_described", "changed_mind", "other"]


class Customer(BaseModel):
    id: int
    name: str
    email: str


class OrderItem(BaseModel):
    sku: str
    name: str
    price: Decimal
    final_sale: bool = False


class Order(BaseModel):
    id: str
    customer_id: int
    delivered_at: date
    total: Decimal
    items: list[OrderItem]

    @property
    def age_days(self) -> int:
        return (date.today() - self.delivered_at).days


class Claim(BaseModel):
    order_id: str | None = None
    reason: Reason = "other"
    skus: list[str] = Field(default_factory=list)
    requested_amount: Decimal | None = None
    language: str = "en"
    needs_clarification: bool = False
    clarification_question: str | None = None


class RuleHit(BaseModel):
    rule_id: str
    effect: Literal["pass", "deny", "escalate", "approve", "info"]
    detail: str


class PolicyParams(BaseModel):
    window_days: int = 30
    review_threshold: Decimal = Decimal("500.00")
    repeat_limit: int = 3
    repeat_window_days: int = 90


class PolicyContext(BaseModel):
    customer_id: int
    claim: Claim
    order: Order | None = None
    recent_refund_count: int = 0
    order_age_days: int | None = None
    flags: list[str] = Field(default_factory=list)
    today: date = Field(default_factory=date.today)


class PolicyResult(BaseModel):
    outcome: Outcome
    refund_amount: Decimal = Decimal("0.00")
    rule_hits: list[RuleHit] = Field(default_factory=list)
    eligible_skus: list[str] = Field(default_factory=list)


class AuditEvent(BaseModel):
    id: int
    request_id: int
    step: str
    detail: dict
    created_at: datetime


class RefundRequest(BaseModel):
    id: int
    customer_id: int
    order_id: str | None
    message: str
    outcome: Outcome
    refund_amount: Decimal
    customer_reply: str
    review_status: Literal["auto", "pending_review", "resolved"]
    appeal_note: str | None = None
    reviewer_note: str | None = None
    source: Literal["user", "seed", "redteam"] = "user"
    created_at: datetime
    resolved_at: datetime | None = None
    receipt: dict = Field(default_factory=dict)
    claim: Claim | None = None
    policy_input: PolicyContext | None = None
    policy_result: PolicyResult | None = None
    audit_events: list[AuditEvent] = Field(default_factory=list)


class RefundCreate(BaseModel):
    customer_id: int = Field(ge=1)
    message: str = Field(min_length=1, max_length=4000)


class AppealCreate(BaseModel):
    customer_id: int = Field(ge=1)
    note: str = Field(min_length=1, max_length=2000)


class ResolveCreate(BaseModel):
    decision: Literal["approved", "denied"]
    note: str = Field(min_length=1, max_length=2000)


class SimulateCreate(BaseModel):
    window_days: int = Field(default=30, ge=1, le=365)
    review_threshold: Decimal = Field(default=Decimal("500.00"), ge=0)
    repeat_limit: int = Field(default=3, ge=1, le=20)


class ClarificationResponse(BaseModel):
    needs_clarification: Literal[True]
    question: str


class RefundResponse(BaseModel):
    request_id: int
    outcome: Outcome
    reply: str
    receipt: dict
