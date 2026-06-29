# ─── iClinic Backend ─────────────────────────────────────────────────────────────
# Multi-stage build for smaller production image

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir redis && \
    pip install --no-cache-dir -e .

# Stage 2: Production image
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY Backend/ /app/Backend
WORKDIR /app/Backend

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
