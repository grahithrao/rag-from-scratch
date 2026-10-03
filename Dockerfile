# ==============================================================================
# RAG From Scratch — Production Multi-Stage Dockerfile
# ==============================================================================

# ---- Stage 1: Build & Dependencies ----
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies in virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Pre-cache the SentenceTransformers embedding model to ensure instant container startup
ENV HF_HOME=/root/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# ---- Stage 2: Final Runtime Image ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install minimal runtime libraries (curl for healthchecks)
RUN apt-get update && apt-get install --no-install-recommends -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for enterprise container security
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -m -s /bin/bash appuser

# Copy virtualenv and cached models from builder
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /root/.cache/huggingface /home/appuser/.cache/huggingface

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/appuser/.cache/huggingface \
    API_HOST=0.0.0.0 \
    API_PORT=8001

# Copy application code and assets
COPY app ./app
COPY frontend ./frontend
COPY scripts ./scripts
COPY sample_report.pdf ./sample_report.pdf
COPY .streamlit ./.streamlit

# Create data directories with appropriate permissions
RUN mkdir -p /app/data/chroma /app/data/uploads && \
    chown -R appuser:appuser /app /home/appuser

# Switch to non-root user
USER appuser

# Expose FastAPI backend (8001) and Streamlit frontend (8501)
EXPOSE 8001 8501

# Healthcheck targeting backend liveness probe
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENTRYPOINT ["/app/scripts/docker_entrypoint.sh"]
CMD ["all"]
