from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from threading import Lock
from typing import Iterable

from app.data import CUSTOMERS, build_orders, prior_refund_counts, seeded_timestamp
from app.models import AuditEvent, Customer, Order, PolicyContext, PolicyResult, RefundRequest


class InMemoryRepository:
    """A small repository with the same boundaries as the SQL-backed version."""

    def __init__(self) -> None:
        self._lock = Lock()
        self.customers: dict[int, Customer] = {c.id: c for c in CUSTOMERS}
        self.orders: dict[str, Order] = {o.id: o for o in build_orders()}
        self.prior_refunds = prior_refund_counts()
        self.requests: dict[int, RefundRequest] = {}
        self.audit: dict[int, list[AuditEvent]] = {}
        self._next_id = 1
        self._next_audit_id = 1

    def seed_dashboard(self, scenarios: Iterable[dict], process_seed) -> None:
        if self.requests:
            return
        for offset, scenario in enumerate(scenarios):
            process_seed(scenario, offset % 14)
        # Add deterministic variants so the dashboard is useful on first boot.
        for index in range(25):
            scenario = list(scenarios)[index % len(list(scenarios))]
            process_seed(
                {
                    **scenario,
                    "customer_id": ((scenario["customer_id"] + index) % 15) + 1,
                    "source": "seed",
                },
                (index + 2) % 14,
            )

    def customer(self, customer_id: int) -> Customer | None:
        return self.customers.get(customer_id)

    def order_for_customer(self, order_id: str | None, customer_id: int) -> Order | None:
        if not order_id:
            return None
        order = self.orders.get(order_id.upper())
        return order if order and order.customer_id == customer_id else None

    def raw_order(self, order_id: str | None) -> Order | None:
        return self.orders.get(order_id.upper()) if order_id else None

    def recent_refund_count(self, customer_id: int) -> int:
        return self.prior_refunds.get(customer_id, 0) + sum(
            1 for request in self.requests.values()
            if request.customer_id == customer_id and request.outcome == "approved"
        )

    def create_request(self, request: RefundRequest) -> RefundRequest:
        with self._lock:
            request.id = self._next_id
            self._next_id += 1
            self.requests[request.id] = request
            self.audit[request.id] = list(request.audit_events)
            return request

    def add_audit(self, request_id: int, step: str, detail: dict) -> AuditEvent:
        with self._lock:
            event = AuditEvent(
                id=self._next_audit_id,
                request_id=request_id,
                step=step,
                detail=detail,
                created_at=datetime.now(timezone.utc),
            )
            self._next_audit_id += 1
            self.audit.setdefault(request_id, []).append(event)
            if request_id in self.requests:
                self.requests[request_id].audit_events.append(event)
            return event

    def get_request(self, request_id: int) -> RefundRequest | None:
        return self.requests.get(request_id)

    def list_requests(self, outcome: str | None = None, review_status: str | None = None, q: str | None = None, limit: int = 50) -> list[RefundRequest]:
        rows = sorted(self.requests.values(), key=lambda item: item.created_at, reverse=True)
        if outcome:
            rows = [row for row in rows if row.outcome == outcome]
        if review_status:
            rows = [row for row in rows if row.review_status == review_status]
        if q:
            needle = q.lower()
            rows = [row for row in rows if needle in row.message.lower() or needle in str(row.order_id).lower()]
        return rows[:limit]

    def update_request(self, request_id: int, **changes) -> RefundRequest | None:
        request = self.requests.get(request_id)
        if not request:
            return None
        for key, value in changes.items():
            setattr(request, key, value)
        return request

    def all_requests(self) -> list[RefundRequest]:
        return list(self.requests.values())


class PostgresRepository(InMemoryRepository):
    """Postgres-backed persistence with the same in-process read model."""

    def __init__(self, database_url: str) -> None:
        super().__init__()
        import json
        from pathlib import Path

        import psycopg
        from psycopg.types.json import Jsonb

        self._Jsonb = Jsonb
        self.db = psycopg.connect(database_url)
        self.db.autocommit = True
        schema_path = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
        self.db.execute(schema_path.read_text(encoding="utf-8"))
        for customer in CUSTOMERS:
            self.db.execute(
                "INSERT INTO customers (id, name, email) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (customer.id, customer.name, customer.email),
            )
        for order in self.orders.values():
            self.db.execute(
                "INSERT INTO orders (id, customer_id, delivered_at, total) VALUES (%s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (order.id, order.customer_id, order.delivered_at, order.total),
            )
            for item in order.items:
                self.db.execute(
                    "INSERT INTO order_items (order_id, sku, name, price, final_sale) SELECT %s, %s, %s, %s, %s WHERE NOT EXISTS (SELECT 1 FROM order_items WHERE order_id=%s AND sku=%s)",
                    (order.id, item.sku, item.name, item.price, item.final_sale, order.id, item.sku),
                )
        for customer_id, count in prior_refund_counts().items():
            existing = self.db.execute("SELECT COUNT(*) FROM prior_refunds WHERE customer_id=%s", (customer_id,)).fetchone()[0]
            for index in range(max(0, count - existing)):
                self.db.execute(
                    "INSERT INTO prior_refunds (customer_id, amount, refunded_at) VALUES (%s, %s, NOW() - (%s || ' days')::interval)",
                    (customer_id, Decimal("25.00"), 30 + index),
                )
        self._load_requests(json)

    def _load_requests(self, json_module) -> None:
        rows = self.db.execute(
            "SELECT id, customer_id, order_id, message, outcome, refund_amount, customer_reply, review_status, appeal_note, reviewer_note, source, created_at, resolved_at, policy_input, policy_result, receipt FROM refund_requests ORDER BY created_at DESC"
        ).fetchall()
        for row in rows:
            policy_input = PolicyContext.model_validate(row[13]) if row[13] else None
            policy_result = PolicyResult.model_validate(row[14]) if row[14] else None
            claim = policy_input.claim if policy_input else None
            request = RefundRequest(
                id=row[0],
                customer_id=row[1],
                order_id=row[2],
                message=row[3],
                outcome=row[4],
                refund_amount=row[5],
                customer_reply=row[6],
                review_status=row[7],
                appeal_note=row[8],
                reviewer_note=row[9],
                source=row[10],
                created_at=row[11],
                resolved_at=row[12],
                policy_input=policy_input,
                policy_result=policy_result,
                claim=claim,
                receipt=row[15] or {},
            )
            self.requests[request.id] = request
            audit_rows = self.db.execute(
                "SELECT id, request_id, step, detail, created_at FROM audit_events WHERE request_id=%s ORDER BY id",
                (request.id,),
            ).fetchall()
            self.audit[request.id] = [
                AuditEvent(id=item[0], request_id=item[1], step=item[2], detail=item[3], created_at=item[4])
                for item in audit_rows
            ]
            request.audit_events = self.audit[request.id]
        if self.requests:
            self._next_id = max(self.requests) + 1
        audit_count = self.db.execute("SELECT COALESCE(MAX(id), 0) FROM audit_events").fetchone()[0]
        self._next_audit_id = int(audit_count) + 1

    def create_request(self, request: RefundRequest) -> RefundRequest:
        row = self.db.execute(
            """
            INSERT INTO refund_requests
              (customer_id, order_id, message, outcome, refund_amount, customer_reply, review_status, appeal_note, reviewer_note, source, created_at, resolved_at, policy_input, policy_result, receipt)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                request.customer_id,
                request.order_id,
                request.message,
                request.outcome,
                request.refund_amount,
                request.customer_reply,
                request.review_status,
                request.appeal_note,
                request.reviewer_note,
                request.source,
                request.created_at,
                request.resolved_at,
                self._Jsonb(request.policy_input.model_dump(mode="json") if request.policy_input else None),
                self._Jsonb(request.policy_result.model_dump(mode="json") if request.policy_result else None),
                self._Jsonb(request.receipt),
            ),
        ).fetchone()
        request.id = row[0]
        self.requests[request.id] = request
        self.audit[request.id] = []
        self._next_id = max(self._next_id, request.id + 1)
        return request

    def add_audit(self, request_id: int, step: str, detail: dict) -> AuditEvent:
        row = self.db.execute(
            "INSERT INTO audit_events (request_id, step, detail) VALUES (%s, %s, %s) RETURNING id, created_at",
            (request_id, step, self._Jsonb(detail)),
        ).fetchone()
        event = AuditEvent(id=row[0], request_id=request_id, step=step, detail=detail, created_at=row[1])
        self.audit.setdefault(request_id, []).append(event)
        if request_id in self.requests:
            self.requests[request_id].audit_events.append(event)
        return event

    def update_request(self, request_id: int, **changes) -> RefundRequest | None:
        request = super().update_request(request_id, **changes)
        if not request:
            return None
        self.db.execute(
            """
            UPDATE refund_requests
            SET outcome=%s, review_status=%s, appeal_note=%s, reviewer_note=%s, customer_reply=%s, resolved_at=%s, refund_amount=%s
            WHERE id=%s
            """,
            (
                request.outcome,
                request.review_status,
                request.appeal_note,
                request.reviewer_note,
                request.customer_reply,
                request.resolved_at,
                request.refund_amount,
                request_id,
            ),
        )
        return request
