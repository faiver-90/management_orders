FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

COPY pyproject.toml README.md /app/

# ставим только runtime-зависимости (без dev)
RUN poetry install --only main --no-ansi \
 && python -c "import uvicorn; print('uvicorn', uvicorn.__version__)" \
 && python -c "import celery; print('celery', celery.__version__)"

COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
