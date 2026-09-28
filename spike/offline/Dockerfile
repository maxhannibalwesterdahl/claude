FROM python:3.12-slim

RUN useradd --create-home --uid 1000 app && mkdir /data && chown app /data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static ./static

USER app
ENV DB_PATH=/data/spike.db
# Lytter kun lokalt: appen deler netværk med tailscale-containeren, som er
# den eneste vej ind (Funnel).
CMD ["uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
