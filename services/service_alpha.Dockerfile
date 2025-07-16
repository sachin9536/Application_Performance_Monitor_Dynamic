FROM python:3.11-slim

WORKDIR /app

COPY services/service_alpha.py /app/service_alpha.py

RUN pip install --no-cache-dir fastapi uvicorn prometheus-client psutil

EXPOSE 8000

CMD ["uvicorn", "service_alpha:app", "--host", "0.0.0.0", "--port", "8000"]