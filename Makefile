.PHONY: install migrate seed backend frontend test build channel-worker channel-maintenance
install:
	python3 -m venv backend/.venv
	backend/.venv/bin/pip install --require-hashes -r backend/requirements-dev.lock
	cd frontend && npm ci
migrate:
	cd backend && .venv/bin/alembic upgrade head
seed:
	cd backend && .venv/bin/python -m app.seed
backend:
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000 --no-access-log
frontend:
	cd frontend && npm run dev
# TEST_DATABASE_URL must explicitly name a disposable database ending in _test.
test:
	cd backend && .venv/bin/pytest -q
build:
	cd frontend && npm run build

channel-worker:
	cd backend && .venv/bin/python -m app.channel_worker
channel-maintenance:
	cd backend && .venv/bin/python -m app.channel_maintenance
