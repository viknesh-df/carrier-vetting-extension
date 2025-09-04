FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY services/billing_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy billing service code
COPY services/billing_service /app/services/billing_service

CMD ["uvicorn", "services.billing_service.app:app", "--host", "0.0.0.0", "--port", "8083", "--reload"]


