.PHONY: run dev install freeze migrate revision up down logs test lint format

run:
	uvicorn app.main:app --reload

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

install:
	pip install -r requirements.txt

freeze:
	pip freeze > requirements.txt

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

revision:
	alembic revision --autogenerate -m "$(m)"

migrate:
	alembic upgrade head

test:
	pytest

lint:
	ruff check .

format:
	ruff format .