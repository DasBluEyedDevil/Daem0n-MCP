FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .
RUN pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd -m -u 1000 daem0nmcp && \
    chown -R daem0nmcp:daem0nmcp /app
USER daem0nmcp

# Create data directory
RUN mkdir -p /home/daem0nmcp/data

# Environment
ENV DAEM0NMCP_STORAGE_PATH=/home/daem0nmcp/data
ENV DAEM0NMCP_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
    CMD python -c "import daem0nmcp" || exit 1

ENTRYPOINT ["python", "-m", "daem0nmcp.server"]
