FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY DedicatedServer/requirements.txt ./DedicatedServer/requirements.txt
RUN pip install --no-cache-dir -r ./DedicatedServer/requirements.txt

COPY DedicatedServer/app ./DedicatedServer/app
COPY SimulationCore/terraformation_sim ./SimulationCore/terraformation_sim
COPY SimulationCore/tests ./SimulationCore/tests

ENV SERVER_PORT=8080
ENV SERVER_MODE=in-memory
ENV PYTHONPATH=/app/SimulationCore:/app/DedicatedServer

WORKDIR /app/DedicatedServer

EXPOSE 8080

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]