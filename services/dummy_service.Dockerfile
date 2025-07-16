FROM python:3.11-slim

WORKDIR /app

COPY services/dummy_service.py /app/dummy_service.py

RUN pip install --no-cache-dir fastapi uvicorn prometheus-client psutil requests

EXPOSE 9000

CMD ["uvicorn", "dummy_service:app", "--host", "0.0.0.0", "--port", "9000"]