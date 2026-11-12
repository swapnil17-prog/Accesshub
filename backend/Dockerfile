# Phase 0: development image (used by docker-compose.yml via `target: dev`).
# Phase 8 adds a hardened multi-stage production target to this file.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

FROM base AS dev
ENV FLASK_APP=wsgi.py \
    FLASK_CONFIG=development
COPY . .
EXPOSE 5000
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000", "--debug"]
