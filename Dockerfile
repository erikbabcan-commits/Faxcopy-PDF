# Frontend dist is committed in this MVP and verified by npm run build in CI.
# No Node or browser engine is needed at runtime.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt \
    && groupadd --gid 10001 presspilot \
    && useradd --uid 10001 --gid 10001 --no-create-home presspilot \
    && mkdir -p /app/data && chown 10001:10001 /app/data
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY frontend/dist /app/web
COPY samples /app/samples
USER 10001:10001
ENV DATA_DIR=/app/data STATIC_DIR=/app/web
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers", "--no-access-log"]
