FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV DATA_DIR=/data \
    SQLITE_PATH=/data/kt.db \
    UPLOAD_DIR=/data/uploads \
    BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8010

VOLUME ["/data"]
EXPOSE 8010

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
