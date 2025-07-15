FROM python:3.11-slim

WORKDIR /app

COPY services/service_beta.py /app/service_beta.py

RUN pip install --no-cache-dir fastapi uvicorn prometheus-client psutil

EXPOSE 8000

CMD ["uvicorn", "service_beta:app", "--host", "0.0.0.0", "--port", "8000"]