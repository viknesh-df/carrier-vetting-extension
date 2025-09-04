FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY services/orchestrator/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy orchestrator service code
COPY services/orchestrator /app/services/orchestrator

# Copy agents and tools
COPY agents /app/agents
COPY tools /app/tools
COPY data /app/data

CMD ["uvicorn", "services.orchestrator.app:app", "--host", "0.0.0.0", "--port", "8081", "--reload"]


