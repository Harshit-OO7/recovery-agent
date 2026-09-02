.PHONY: install dev seed run-batch test

install:
	cd backend && python -m pip install -r requirements.txt

dev:
	cd backend && python -m uvicorn app.main:app --reload --port 8000

test:
	cd backend && python -m pytest -v tests/

seed:
	cd backend && python -m app.data.seed

run-batch:
	cd backend && python -m app.orchestrator.runner
