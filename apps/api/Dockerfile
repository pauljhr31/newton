# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN useradd --create-home --uid 10001 newton

FROM base AS runtime
COPY requirements.lock ./
RUN pip install -r requirements.lock
COPY alembic.ini ./
COPY migrations ./migrations
COPY newton ./newton
USER newton
EXPOSE 8000
CMD ["uvicorn", "newton.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM runtime AS dev
USER root
COPY requirements-dev.lock ./
RUN pip install -r requirements-dev.lock
COPY tests ./tests
COPY pyproject.toml ./
USER newton
