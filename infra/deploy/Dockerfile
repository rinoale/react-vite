FROM mabi-ocr-models AS models

FROM python:3.14.2-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    pkg-config \
    rustc \
    cargo \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/ /app/backend/
COPY configs/ /app/configs/
COPY data/dictionary/ /app/data/dictionary/
COPY data/source_of_truth/ /app/data/source_of_truth/
COPY scripts/ /app/scripts/

# Overlay resolved model files from the models image
COPY --from=models /models/ /app/backend/ocr/models/

# Frontend SPA (pre-built dist)
COPY frontend/ /app/frontend/

COPY startup.sh /app/startup.sh
RUN chmod +x /app/startup.sh

WORKDIR /app/backend

EXPOSE 8000

CMD ["/app/startup.sh"]
