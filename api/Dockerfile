# FastAPI Enrichment Service Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies using uv
RUN uv sync --no-dev --no-cache

# Copy application code
COPY api/ ./api/

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Run FastAPI with uvicorn
CMD ["uv", "run", "uvicorn", "api.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
