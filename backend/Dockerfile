FROM python:3.14.2-slim

WORKDIR /app

# System deps commonly needed by OCR stack (opencv/easyocr/pillow)
# and source builds when wheels are unavailable on Python 3.14.
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

# Mount source at runtime, but keep a baseline copy for image completeness.
COPY backend /app/backend
COPY configs /app/configs

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--reload", "--port", "8000"]
