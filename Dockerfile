# syntax=docker/dockerfile:1
# PREDAIOT — single reproducible image. The SAME image runs identically on a
# laptop, Docker, Render, AWS, an industrial plant, or an air-gapped factory —
# the portability that is a core competitive advantage. The economic engine is
# byte-identical across all of them; only the (env-driven) infrastructure differs.
#
# NOTE: validated by the CI `docker-build` job (this environment has no Docker).

# ---- Stage 1: build the Vite frontend ----------------------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend serving the built frontend ----------------------
FROM python:3.12.6-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000
WORKDIR /app

# Locked, reproducible dependency install (exact validated closure).
COPY backend/requirements.lock ./requirements.lock
RUN pip install -r requirements.lock

# Backend source.
COPY backend/ ./

# Built frontend at the path main.py's static mount resolves: /app/../frontend/dist
COPY --from=frontend /fe/dist /frontend/dist

# Bake build identity so GET /version works even air-gapped (no RENDER_GIT_COMMIT).
ARG GIT_SHA=unknown
RUN echo "$GIT_SHA" > VERSION

EXPOSE 8000
# Honours $PORT (Render/PaaS) and defaults to 8000 (Docker/on-prem).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
