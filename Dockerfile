# Madplan: SvelteKit-frontend bygget statisk og serveret af FastAPI-backend.
# Bygges fra repoets rod:  docker build -t madplan .

FROM node:24-slim AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN useradd --create-home --uid 1000 app && mkdir /data && chown app /data
WORKDIR /app
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/pyproject.toml ./
COPY backend/src ./src
RUN pip install --no-cache-dir --no-deps .
COPY --from=frontend /src/build ./static

USER app
ENV DATA_DIR=/data STATIC_DIR=/app/static
EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
# Kan kun nås fra tailscale-containeren på det interne Docker-netværk, så
# X-Forwarded-For fra den kan stoles på.
CMD ["uvicorn", "--factory", "madplan.api:create_app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
