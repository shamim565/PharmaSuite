# PharmaSuite — developer entry points
#
# `make up` starts PostgreSQL, Redis, the API, Celery worker/beat and the
# Next.js dev server. The first run builds the backend image and installs
# frontend dependencies, so it can take a few minutes.

COMPOSE ?= docker compose -f infra/docker-compose.yml
PY      ?= uv run
API_URL ?= http://localhost:8000/api/v1

.DEFAULT_GOAL := help

.PHONY: help up down logs ps db migrate test test-docker lint coverage seed-rbac seed-demo api web shell clean

help:
	@echo "PharmaSuite"
	@echo ""
	@echo "  make up          start the full stack (db, redis, api, worker, beat, web)"
	@echo "  make seed-demo   load the demo dataset (branches, catalog, sales, payments)"
	@echo "  make down        stop the stack"
	@echo "  make logs        follow container logs"
	@echo ""
	@echo "  make test        run backend tests on the host (needs Docker db + .env)"
	@echo "  make test-docker run backend tests inside the api container"
	@echo "  make lint        ruff (backend) + tsc (frontend)"
	@echo "  make coverage    measured coverage report"
	@echo ""
	@echo "  make api         run Django on the host at :8000"
	@echo "  make web         run Next.js on the host at :3000"
	@echo "  make migrate     apply migrations inside the api container"
	@echo "  make shell       Django shell inside the api container"

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

db:
	$(COMPOSE) up -d --wait postgres redis

migrate:
	$(COMPOSE) exec -T web $(PY) python manage.py migrate

seed-rbac:
	$(COMPOSE) exec -T web $(PY) python manage.py seed_rbac

seed-demo:
	$(COMPOSE) exec -T web $(PY) python manage.py seed_demo

test:
	cd backend && $(PY) pytest

test-docker:
	$(COMPOSE) exec -T web $(PY) pytest

lint:
	cd backend && $(PY) ruff check .
	cd frontend && npm run lint
	cd frontend && npm run format:check
	cd frontend && npm run typecheck

coverage:
	cd backend && $(PY) coverage run -m pytest && $(PY) coverage report -m

api:
	cd backend && $(PY) python manage.py runserver 8000

web:
	cd frontend && npm run dev

shell:
	$(COMPOSE) exec web $(PY) python manage.py shell

clean:
	@echo "This deletes the PostgreSQL volume and all demo data."
	$(COMPOSE) down -v
