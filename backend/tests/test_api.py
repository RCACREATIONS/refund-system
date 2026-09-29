from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app, rate_limiter


@pytest.fixture()
def client() -> Iterator[TestClient]:
    rate_limiter.hits.clear()
    with TestClient(app) as test_client:
        yield test_client
    rate_limiter.hits.clear()


def admin_headers() -> dict[str, str]:
    return {"X-Admin-Token": "admin-demo-token"}


def submit(client: TestClient, customer_id: int, message: str):
    return client.post(
        "/api/refunds",
        json={"customer_id": customer_id, "message": message},
    )


def test_admin_authentication_is_required(client: TestClient):
    assert client.get("/api/admin/stats").status_code == 401
    response = client.get("/api/admin/stats", headers=admin_headers())
    assert response.status_code == 200
    assert response.json()["total"] >= 40


def test_customer_cannot_read_another_customer_request(client: TestClient):
    response = submit(
        client,
        1,
        "My headphones arrived cracked. Order ORD-1001, please refund it.",
    )
    assert response.status_code == 200
    request_id = response.json()["request_id"]

    assert client.get(f"/api/refunds/{request_id}?customer_id=2").status_code == 404
    assert client.get(f"/api/refunds/{request_id}?customer_id=1").status_code == 200


def test_rate_limit_returns_429_after_window_capacity(client: TestClient):
    original_limit = rate_limiter.limit
    rate_limiter.limit = 2
    try:
        messages = [
            "My headphones arrived cracked. Order ORD-1001, please refund it.",
            "The kettle was sent wrong. Order ORD-1005, please refund it.",
            "My lamp is broken. Order ORD-1006, please refund it.",
        ]
        responses = [submit(client, 1, message) for message in messages]
        assert [response.status_code for response in responses] == [200, 200, 429]
        assert responses[-1].json()["detail"]["error"] == "rate_limited"
    finally:
        rate_limiter.limit = original_limit


def test_appeal_moves_denial_to_pending_review(client: TestClient):
    response = submit(
        client,
        2,
        "I want my money back for the limited edition sneakers, ORD-1002. They don't fit.",
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "denied"
    request_id = response.json()["request_id"]

    appeal = client.post(
        f"/api/refunds/{request_id}/appeal",
        json={"customer_id": 2, "note": "Please have a specialist reconsider this request."},
    )
    assert appeal.status_code == 200
    assert appeal.json()["review_status"] == "pending_review"

    customer_view = client.get(f"/api/refunds/{request_id}?customer_id=2")
    assert customer_view.status_code == 200
    assert customer_view.json()["review_status"] == "pending_review"
    assert customer_view.json()["outcome"] == "escalated"


def test_human_resolution_updates_customer_reply(client: TestClient):
    response = submit(
        client,
        4,
        "The laptop in ORD-1004 has a dead pixel cluster and bent hinge. Full refund please.",
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "escalated"
    request_id = response.json()["request_id"]

    resolved = client.post(
        f"/api/admin/requests/{request_id}/resolve",
        headers=admin_headers(),
        json={"decision": "approved", "note": "Verified the reported damage with the customer."},
    )
    assert resolved.status_code == 200
    body = resolved.json()["request"]
    assert body["review_status"] == "resolved"
    assert body["outcome"] == "approved"
    assert "approved" in body["customer_reply"].lower()

    customer_view = client.get(f"/api/refunds/{request_id}?customer_id=4")
    assert customer_view.status_code == 200
    assert customer_view.json()["review_status"] == "resolved"
    assert "approved" in customer_view.json()["customer_reply"].lower()