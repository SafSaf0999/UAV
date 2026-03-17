FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and serial
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV EDGE_CONFIG=/app/config.yaml

ENTRYPOINT ["python", "main.py"]
