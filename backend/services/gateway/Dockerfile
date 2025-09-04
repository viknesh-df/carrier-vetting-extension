FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY services/gateway/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy contracts for imports
COPY contracts /app/contracts

# Copy gateway service code
COPY services/gateway /app/services/gateway

CMD ["uvicorn", "services.gateway.app:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]


