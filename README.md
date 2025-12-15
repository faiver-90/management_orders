# Order Service (FastAPI)

Implements the requirements from the provided technical assignment:
- FastAPI + Swagger UI
- PostgreSQL (SQLAlchemy 2.x async) + Alembic
- JWT auth (OAuth2 password flow)
- Redis cache for orders (TTL 5 minutes)
- RabbitMQ for `new_order` event (async publisher) + consumer that enqueues Celery task
- Celery background processing task
- CORS + rate limiting middleware
- Secrets via `.env` using `pydantic-settings`
- Ruff + mypy + pytest with 100% coverage

## Quick start (Docker)

1) Create env:
```bash
cp .env.example .env
```

2) Run:
```bash
docker compose up --build
```

3) Open Swagger:
- http://localhost:8000/docs

## Local dev (Poetry)

```bash
poetry install
poetry run uvicorn app.main:app --reload
```

## Tests

```bash
poetry run pytest
poetry run ruff check .
poetry run mypy .
```

## Services

- `api`: HTTP endpoints
- `db`: database models/session
- `services`: cache, messaging, order business logic
- `tasks`: Celery app and tasks
- `middleware`: rate limiting
#   m e n e g m n t _ o r d e r s 
