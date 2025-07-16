FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY services/order_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/order_service/app ./app
COPY utils ./utils

ENV PYTHONPATH="/app"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]