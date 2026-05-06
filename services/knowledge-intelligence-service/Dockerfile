FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir \
        "fastapi>=0.135.1" \
        "uvicorn[standard]>=0.42.0" \
        "sqlalchemy[asyncio]>=2.0.41" \
        "asyncpg>=0.31.0" \
        "cloud-sql-python-connector[asyncpg]>=1.16.0" \
        "cryptography>=43.0.3"

COPY src ./src

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
