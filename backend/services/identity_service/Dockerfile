FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY services/identity_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy identity service code
COPY services/identity_service /app/services/identity_service

CMD ["uvicorn", "services.identity_service.app:app", "--host", "0.0.0.0", "--port", "8082", "--reload"]


