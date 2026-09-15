install:
	python -m pip install -e '.[dev]'

frontend-install:
	npm --prefix frontend ci

test:
	pytest -q

lint:
	ruff check .
	ruff format --check .

frontend-lint:
	npm --prefix frontend run lint

frontend-build:
	npm --prefix frontend run build

check: test lint frontend-lint frontend-build

run:
	uvicorn app.main:app --reload

frontend-run:
	npm --prefix frontend run dev

migrate:
	alembic upgrade head

migration:
	alembic revision --autogenerate -m "describe change"

bootstrap-admin:
	python scripts/bootstrap_admin.py admin@example.com

index:
	python scripts/create_index.py
