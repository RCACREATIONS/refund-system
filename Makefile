.PHONY: up down test seed redteam frontend

up:
	docker-compose up --build

down:
	docker-compose down

test:
	pytest -q backend/tests
	npm run typecheck
	npm run build

seed:
	curl -fsS http://localhost:8000/api/health

redteam:
	curl -fsS -X POST -H "X-Admin-Token: $${ADMIN_TOKEN:-admin-demo-token}" http://localhost:8000/api/admin/redteam/run

frontend:
	npm run dev
