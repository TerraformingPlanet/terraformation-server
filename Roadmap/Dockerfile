FROM python:3.12-slim

WORKDIR /app

# ── system deps (h3 needs gcc/g++) ────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ cmake \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Persistent SQLite database
VOLUME ["/data"]

# Workspace mount for pytest runs (mounted read-only from host)
# docker-compose maps ../:/workspace:ro
ENV WORKSPACE_PATH=/workspace
ENV DB_PATH=/data/roadmap.db
ENV PORT=8001

EXPOSE 8001

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.create_connection(('localhost', 8001), 2.0); s.close()" || exit 1

CMD ["python", "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8001"]
