FROM python:3.14.2-slim

ARG UID=1000
ARG GID=1000
ARG REQUIREMENTS=requirements.txt

WORKDIR /app

# System deps for source builds when wheels are unavailable on Python 3.14,
# and runtime libs for opencv/pillow (worker image).
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

COPY backend/requirements*.txt /app/
RUN pip install --no-cache-dir -r /app/${REQUIREMENTS}

# Mount source at runtime, but keep a baseline copy for image completeness.
COPY backend /app/backend
COPY configs /app/configs

# Create non-root user (python-slim has no UID 1000 conflict)
RUN groupadd -g ${GID} appgroup \
 && useradd -m -u ${UID} -g ${GID} -s /bin/bash appuser \
 && chown -R ${UID}:${GID} /app

ENV PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app/backend

USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--reload", "--port", "8000"]
