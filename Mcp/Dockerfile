FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV MCP_TRANSPORT=http
ENV MCP_PORT=8000
ENV GAME_BRIDGE_URL=http://host.docker.internal:48621

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import socket; s = socket.create_connection(('localhost', 8000), 2.0); s.close()" || exit 1

CMD ["python", "server.py"]