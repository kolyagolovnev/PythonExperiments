# ---------- Стадия 1: общая база (только прод-зависимости) ----------
FROM python:3.12-slim AS base

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Системные зависимости для прода (psycopg и т.п.)
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код копируем в base — но перезапишем в prod, если нужно
COPY . .


# ---------- Стадия 2: PROD (без dev-зависимостей) ----------
FROM base AS prod

# Ничего лишнего: только код и прод-пакеты
# Если нужен непривилегированный пользователь:
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------- Стадия 3: TEST-BASE ----------
FROM base AS test-base

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

ENV TESTING=1


# ---------- Стадия 3.5: LINT (mypy) ----------
FROM test-base AS lint

# Конфиг mypy читается из pyproject.toml или mypy.ini
CMD ["mypy", "services/", "domains/", "--show-error-codes"]


# ---------- Стадия 4: TEST-UNIT ----------
FROM test-base AS test-unit
CMD ["pytest", "tests/unit", "-v", "--tb=short"]


# ---------- Стадия 5: TEST-E2E ----------
FROM test-base AS test-e2e
CMD ["pytest", "tests/e2e", "-v", "--tb=short"]