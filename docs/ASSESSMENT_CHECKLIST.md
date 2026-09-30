# WORKNOON assessment evidence

This checklist maps the supplied Full Stack AI Integration Product Challenge to the RefundDesk implementation.

## Core requirements

| Assessment requirement | Evidence |
| --- | --- |
| Approximately 15 synthetic customers and order histories | `backend/app/data.py` contains 15 customers, 15 primary orders, historical orders, and prior refund history. |
| Refund policy document | `docs/refund-policy.md` defines R1–R8, boundaries, and precedence. |
| Backend API | FastAPI routes in `backend/app/main.py`; OpenAPI is available at `/docs`. |
| Customer/order lookup and policy application | `backend/app/repository.py`, `backend/app/policy/engine.py`, and `backend/app/pipeline.py`. |
| AI integration | `backend/app/ai/client.py` provides deterministic Mock AI and optional OpenAI-compatible live mode. |
| Approved, denied, and escalated outcomes | The 15 scenario cases and policy tests cover all three outcomes. |
| Prompt-injection safeguards | Normalization, multilingual and heuristic screening, untrusted prompt framing, canary checks, typed outputs, reconciliation, and reply firewall. |
| Customer interface | React chat at `/` with scenario picker, typing state, receipts, errors, appeals, and polling. |
| Support dashboard | Admin console at `/admin` with token gate, stats, queue filters, audit drawer, resolution, Trust Lab, and Policy Simulator. |

## Deliverables

- Public repository: `RCACREATIONS/refund-system`
- Container stack: `docker-compose.yml` starts PostgreSQL, FastAPI, and nginx-served React.
- Fresh-clone configuration: Compose uses `${VAR:-default}` values and works in Mock AI mode without `.env` or a paid API key.
- Documentation: `README.md`, `.env.example`, `docs/refund-policy.md`, and this checklist.
- Demo walkthrough: `docs/DEMO_SCRIPT.md`; the current customer screen is shown in `docs/assets/customer-chat.jpg`.
- License and repository hygiene: `LICENSE` and `.gitignore`; secrets are supplied only through environment variables.

## Verification commands

```bash
PYTHONPATH=backend pytest -q backend/tests
npm run typecheck
npm run build
PYTHONPATH=backend python -m app.security.run
docker-compose up --build
```

The Docker command must be run on a machine with a Docker daemon. The Replit preview intentionally uses the in-memory repository so it remains free and starts without a database service.