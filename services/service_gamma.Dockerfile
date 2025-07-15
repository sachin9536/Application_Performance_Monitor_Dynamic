FROM python:3.11-slim

WORKDIR /app

COPY services/service_gamma.py /app/service_gamma.py

RUN pip install --no-cache-dir fastapi uvicorn prometheus-client psutil

EXPOSE 8000

CMD ["uvicorn", "service_gamma:app", "--host", "0.0.0.0", "--port", "8000"]