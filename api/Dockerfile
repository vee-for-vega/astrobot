# Multi-stage build. Stage 1 installs deps; stage 2 ships the runtime image
# without build tooling. Smaller image, faster ECR pulls.

FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Build deps for any wheels that need to compile from source.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Pre-download HF models so the first request isn't a 30s model load.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/src \
    HF_HOME=/home/app/.cache/huggingface

# Non-root user for the runtime.
RUN useradd --create-home --shell /bin/bash app

# Copy installed packages and pre-downloaded HF cache from builder.
COPY --from=builder --chown=app:app /root/.local /home/app/.local
COPY --from=builder --chown=app:app /root/.cache/huggingface /home/app/.cache/huggingface

ENV PATH=/home/app/.local/bin:$PATH

WORKDIR /app

# Copy app code and the prebuilt vector store + DistilBERT model.
COPY --chown=app:app api/ ./api/
COPY --chown=app:app src/ ./src/
COPY --chown=app:app data/ ./data/
COPY --chown=app:app models/ ./models/

# bot_controller writes to /app/logs at import time. WORKDIR is root-owned;
# create the dir with app ownership so the non-root runtime user can write.
RUN mkdir -p /app/logs && chown -R app:app /app/logs

USER app

EXPOSE 8000

# uvicorn with one worker. The bot keeps state (Chroma, BERT) in process memory;
# multiple workers would each load a copy and waste RAM on a t3.small.
CMD ["uvicorn", "api.api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
