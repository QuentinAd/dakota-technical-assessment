# Dagster orchestration service Dockerfile
FROM python:3.13-slim

# Set working directory
WORKDIR /opt/dagster/app

# Install system dependencies (including LaTeX for PDF export)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    git \
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-plain-generic \
    pandoc \
    && rm -rf /var/lib/apt/lists/*

# Copy project dependencies
COPY pyproject.toml uv.lock README.md ./

# Install uv package manager
RUN pip install --no-cache-dir uv

# Install project dependencies
RUN uv sync --all-extras

# Copy ingestion module (needed by Dagster assets)
COPY ingestion /opt/dagster/app/ingestion

# Copy dbt project (needed for transformations)
COPY dbt /opt/dagster/app/dbt

# Copy reports module (needed by report generation asset)
COPY reports /opt/dagster/app/reports

# Copy Dagster project
COPY orchestration/dagster_project /opt/dagster/app/dagster_project

# Copy startup script and convert line endings from Windows to Unix
COPY orchestration/start-dagster.sh /opt/dagster/app/start-dagster.sh
RUN sed -i 's/\r$//' /opt/dagster/app/start-dagster.sh && chmod +x /opt/dagster/app/start-dagster.sh

# Create directory for compute logs
RUN mkdir -p /opt/dagster/compute_logs

# Expose Dagster webserver port
EXPOSE 3000

# Set environment variables
ENV DAGSTER_HOME=/opt/dagster/app
ENV PYTHONUNBUFFERED=1

# Run both Dagster daemon and webserver
CMD ["bash", "/opt/dagster/app/start-dagster.sh"]
