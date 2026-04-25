FROM python:3.11-slim

WORKDIR /app

COPY main/control-center/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main/control-center/ /app/control_center/

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

ENTRYPOINT ["sh", "-c", "uvicorn control_center.app:app --host 0.0.0.0 --port ${CONTROL_CENTER_PORT:-8080}"]
