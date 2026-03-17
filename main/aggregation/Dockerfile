FROM python:3.11-slim

WORKDIR /app

COPY main/aggregation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main/aggregation/ /app/main/aggregation/
COPY shared/ /app/shared/
COPY main/__init__.py /app/main/__init__.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["sh", "-c", "uvicorn main.aggregation.app:app --host 0.0.0.0 --port ${AGGREGATION_PORT:-8001}"]
