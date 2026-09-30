# RefundDesk

RefundDesk is an AI-assisted customer-support refund system built around a simple trust boundary: **AI proposes, deterministic policy code disposes**. A customer can describe a refund request in natural language, while the policy engine calculates the eligible amount from order facts, applies hard denials and review rules, and produces a customer-safe decision receipt. Support staff get an auditable queue, a Trust Lab that attacks the system, and a Policy Simulator that replays historical decisions under proposed policy changes.

![RefundDesk customer chat](docs/assets/customer-chat.jpg)

## Quick start

```bash
cp .env.example .env
docker-compose up --build
```

Open [http://localhost:3000](http://localhost:3000) for the customer chat and [http://localhost:3000/admin](http://localhost:3000/admin) for the support console. The default admin token is `admin-demo-token`. The third command for a local Python/Node workflow is:

```bash
pytest -q backend/tests
npm install && npm run build
```

The app works without an API key in deterministic **Mock AI mode**. To use a real OpenAI-compatible provider, set `LLM_API_KEY`, and optionally `LLM_BASE_URL` and `LLM_MODEL` in `.env`. Presets are documented in `.env.example`. All Docker Compose values use `${VAR:-default}` substitution, so a fresh clone does not require a `.env` file.

## Architecture

```text
React (TypeScript) ── nginx ── /api ──> FastAPI
                                  ├─ routes: validation and HTTP status
                                  ├─ pipeline: the only stage orchestrator
                                  ├─ policy: pure deterministic engine
                                  ├─ ai: provider abstraction and mock mode
                                  ├─ security: injection heuristics and Trust Lab
                                  ├─ simulator: policy replay
                                  └─ repository: plain data access boundary
                                         │
                                  PostgreSQL schema / demo repository
```

The pipeline runs:

1. `input_screen` and `extraction` in parallel.
2. `context`, using the authenticated/demo customer ID rather than customer text.
3. `policy_input`, storing the exact replayable snapshot.
4. `policy`, using pure code and database-derived money amounts.
5. `ai_review`, which can only raise caution.
6. `reconcile`, taking the stricter result.
7. `reply`, followed by the reply firewall.
8. `persist`, with one audit event per stage.

The repository includes a PostgreSQL schema for Compose deployments and an in-memory demo repository for the Replit preview. This keeps the free preview useful without requiring a database process, while the schema and Compose service are ready for the assessment's containerized deployment.

When `USE_DATABASE=true`, the backend retries the PostgreSQL connection during startup instead of silently starting against the in-memory repository. This makes Compose startup resilient to the database healthcheck settling.

## How the AI integration works

`LLMClient` is a small provider protocol. `MockClient` is the default and uses deterministic regex and keyword extraction, heuristic screening, policy-aware review, and templates. It reproduces the scenario picker without a paid key. `OpenAICompatClient` uses `httpx` against `/chat/completions` with JSON mode and falls back safely to the mock extractor/reviewer/replier when a live call is unavailable.

The model never receives tools, database write access, or authority over customer identity, outcome, or money. It sees customer text as untrusted data. The safeguards are layered:

- Unicode normalization, control-character stripping, length limits, and escaped customer delimiters.
- Heuristic injection screening for overrides, fake roles, exfiltration, encoded payloads, social engineering, and outcome-mimicking JSON.
- A separate screen classifier rather than asking extraction to decide whether text is safe.
- Strict Pydantic validation and deterministic reconciliation.
- A per-process canary that triggers escalation and a template reply if leaked.
- A reply firewall that blocks internal rule IDs, thresholds, safety vocabulary, mismatched outcomes, and incorrect amounts.
- Neutral customer-facing language for flagged requests.

These defenses reduce risk; they do not claim that a live model is infallible. The deterministic engine remains the final authority.

## Policy

| ID | Rule |
|---|---|
| R1 | Final-sale items are not refundable; mixed orders assess eligible non-final-sale items. |
| R2 | Requests are valid through day 30 after delivery; day 31 is expired. |
| R3 | Amounts above $500 require human review; exactly $500 can auto-approve. |
| R4 | Damaged, incorrect, and not-as-described items can be approved in-window. |
| R5 | The order must belong to the requesting customer. |
| R6 | Three or more refunds in 90 days require review. |
| R7 | Suspicious, conflicting, unclear, or item-mismatched requests escalate. |
| R8 | In-window change-of-mind returns for eligible items can be approved. |

Hard denials (R5, R1, R2) beat escalations (R3, R6, R7), which beat approvals (R4, R8). Read the full customer-readable policy in `docs/refund-policy.md`.

## Trust Lab and Policy Simulator

The support console includes:

- **Trust Lab:** `POST /api/admin/redteam/run` sends the attack corpus through the actual pipeline and grades that attacks do not become approvals and replies remain customer-safe.
- **Policy Simulator:** `POST /api/admin/simulate` replays stored `policy_input` snapshots through the pure engine without any LLM calls. It reports changed outcomes and refund exposure.

Both are available from the admin UI. Use the default admin token for the demo.

## API overview

```bash
curl http://localhost:8000/api/health

curl -X POST http://localhost:8000/api/refunds \
  -H 'Content-Type: application/json' \
  -d '{"customer_id":1,"message":"My headphones arrived cracked. Order ORD-1001."}'

curl http://localhost:8000/api/admin/stats \
  -H 'X-Admin-Token: admin-demo-token'
```

Customer endpoints include health, demo customers, scenarios, refund submission, customer-safe request lookup, and appeals. Admin endpoints include filtered requests, full audits, stats, resolution, simulation, and red-team execution. FastAPI OpenAPI docs are at `/docs`.

## Testing

```bash
pytest -q backend/tests
npm run typecheck
npm run build
```

`Makefile` also provides `up`, `down`, `test`, `seed`, and `redteam`. The tests cover policy boundaries, scenario outcomes and amounts, injectable policy parameters, prompt-injection screening, API operations, the full 24-case Trust Lab corpus, and precedence safety. The standalone runner is `PYTHONPATH=backend python -m app.security.run`. In a full Docker environment, use the cold-start checklist below to exercise all 15 picker scenarios.

## Assumptions and trade-offs

- There is no real authentication; the demo customer selector represents a known authenticated customer, and the admin console uses one environment token.
- The Replit preview uses the in-memory repository for a no-cost, no-service startup; Docker includes PostgreSQL 16 and an idempotent schema for the containerized path.
- An in-memory sliding-window rate limit is used instead of Redis.
- This is single-tenant and has one policy configuration.
- Plain SQL/schema boundaries are preferred to an ORM.
- Customer updates poll rather than using WebSockets.
- The policy engine is code with injectable parameters; the simulator previews changes without making them live.
- No real payments, email, refunds, or external authentication are performed.

## Assessment evidence

See [`docs/ASSESSMENT_CHECKLIST.md`](docs/ASSESSMENT_CHECKLIST.md) for a requirement-by-requirement map of the supplied WORKNOON challenge to the source files, UI routes, and verification commands.

## Cold-start checklist

From a fresh clone:

1. Run `docker-compose up --build` with no `.env`.
2. Open `http://localhost:3000`, run every scenario in the picker, and compare each receipt with the expected outcome in `backend/app/data.py`.
3. Repeat with `LLM_API_KEY` set to an OpenAI-compatible provider.
4. Run `docker-compose down -v && docker-compose up` to confirm clean reseeding.

## What I’d do next

Add real customer authentication, Redis-backed rate limiting, a durable queue for LLM calls, per-tenant policies, structured observability, and a feedback loop that turns human resolutions into extraction and safety evaluation data.
