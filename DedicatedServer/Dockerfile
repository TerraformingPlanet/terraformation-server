FROM python:3.12-slim

WORKDIR /app

COPY DedicatedServer/requirements.txt ./DedicatedServer/requirements.txt
RUN pip install --no-cache-dir -r ./DedicatedServer/requirements.txt

COPY DedicatedServer/app ./DedicatedServer/app
COPY SimulationCore/terraformation_sim ./SimulationCore/terraformation_sim

ENV SERVER_PORT=8080
ENV SERVER_MODE=in-memory
ENV PYTHONPATH=/app/SimulationCore:/app/DedicatedServer

WORKDIR /app/DedicatedServer

EXPOSE 8080

CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]