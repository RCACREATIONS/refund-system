# RefundDesk

## Run in Replit

The Replit preview uses one workflow that starts the FastAPI service on port 8000 and the Vite frontend on port 5000:

```bash
PYTHONPATH=backend python backend/run.py & npm run dev
```

The app defaults to deterministic Mock AI mode when `LLM_API_KEY` is empty. The support console uses `ADMIN_TOKEN`, which defaults to `admin-demo-token`. For the containerized assessment path, use `docker-compose up --build`; it starts Postgres, FastAPI, and nginx on ports 8000 and 3000.

## Checks

```bash
PYTHONPATH=backend pytest -q backend/tests
npm run typecheck
npm run build
```
