FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY services/connectors_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy connectors service code
COPY services/connectors_service /app/services/connectors_service

CMD ["uvicorn", "services.connectors_service.app:app", "--host", "0.0.0.0", "--port", "8084", "--reload"]


