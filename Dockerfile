# Frontend dist is committed in this MVP and verified by npm run build in CI.
# No Node or browser engine is needed at runtime.
FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app/backend
COPY backend/requirements-postgres.lock ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements-postgres.lock \
    && groupadd --gid 10001 presspilot \
    && useradd --uid 10001 --gid 10001 --no-create-home presspilot \
    && mkdir -p /app/data && chown 10001:10001 /app/data
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY frontend/dist /app/web
COPY samples /app/samples
# Checkout umask must not make root-owned application files unreadable at runtime.
RUN chmod -R a+rX /app/backend /app/web /app/samples
USER 10001:10001
ENV DATA_DIR=/app/data STATIC_DIR=/app/web
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--no-proxy-headers", "--no-access-log"]
