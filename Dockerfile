FROM node:22-alpine AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
RUN npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend \
    ONELAP_SERVE_FRONTEND=true \
    PORT=10000

WORKDIR /app

COPY backend/requirements.txt backend/requirements-journal.txt backend/requirements-ai.txt backend/requirements-tracing.txt ./backend/
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
    -r backend/requirements-journal.txt \
    -r backend/requirements-ai.txt \
    -r backend/requirements-tracing.txt

COPY backend/onelap ./backend/onelap
COPY datasets/onelap-sft-v1.manifest.json ./datasets/onelap-sft-v1.manifest.json
COPY --from=frontend /build/dist ./dist

RUN addgroup --system onelap \
    && adduser --system --ingroup onelap --home /home/onelap onelap \
    && mkdir -p /app/.data \
    && chown onelap:onelap /app/.data

USER onelap

EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/health', timeout=3)"
CMD ["sh", "-c", "exec uvicorn onelap.main:create_app --factory --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --no-proxy-headers"]
