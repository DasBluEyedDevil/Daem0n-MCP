# Docker Design

**Date:** 2025-12-04
**Status:** Approved
**Scope:** Containerize DevilMCP for isolation, reproducibility, and safety

---

## Problem Statement

Current state:
- `pip install -e .` pollutes system Python
- Dependency conflicts with user's other projects
- ProcessManager executes commands on host system (security risk)
- Environment setup varies across machines

---

## Design

### File Structure

```
DevilMCP/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
└── docker/
    └── entrypoint.sh
```

### Dockerfile

```dockerfile
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
RUN useradd -m -u 1000 devilmcp && \
    chown -R devilmcp:devilmcp /app
USER devilmcp

# Create data directory
RUN mkdir -p /home/devilmcp/data

# Environment
ENV DEVILMCP_STORAGE_PATH=/home/devilmcp/data
ENV DEVILMCP_LOG_LEVEL=INFO
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
    CMD python -c "import devilmcp" || exit 1

ENTRYPOINT ["python", "-m", "devilmcp.server"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  devilmcp:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: devilmcp
    volumes:
      # Persistent storage for database
      - devilmcp-data:/home/devilmcp/data
      # Mount user's project read-only for analysis
      - ${PROJECT_PATH:-.}:/workspace:ro
    environment:
      - DEVILMCP_PROJECT_ROOT=/workspace
      - DEVILMCP_LOG_LEVEL=${LOG_LEVEL:-INFO}
    # Required for MCP stdio transport
    stdin_open: true
    tty: true
    restart: unless-stopped

volumes:
  devilmcp-data:
    driver: local
```

### .dockerignore

```
# Git
.git
.gitignore
.worktrees

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
venv/
env/
.venv/
*.egg-info/
dist/
build/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Project specific
.env
.devilmcp/
storage/
*.db
*.log

# Docs (not needed in container)
docs/
*.md
!README.md

# Tests (optional - include for dev builds)
# tests/
```

### docker/entrypoint.sh

```bash
#!/bin/bash
set -e

# Run migrations if enabled
if [ "$DEVILMCP_AUTO_MIGRATE" != "false" ]; then
    echo "Running database migrations..."
    python -c "from devilmcp.database import run_migrations; run_migrations()"
fi

# Start server
exec python -m devilmcp.server "$@"
```

---

## Usage

### Build and Run

```bash
# Build image
docker compose build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

### One-liner for AI Agents

```bash
# Quick start with current directory as project
PROJECT_PATH=$(pwd) docker compose up -d
```

### MCP Configuration for Docker

```json
{
  "mcpServers": {
    "devilmcp": {
      "command": "docker",
      "args": ["compose", "-f", "/path/to/DevilMCP/docker-compose.yml", "run", "--rm", "devilmcp"],
      "env": {
        "PROJECT_PATH": "/path/to/user/project"
      }
    }
  }
}
```

---

## Security Features

| Feature | Implementation |
|---------|----------------|
| Non-root user | `useradd devilmcp`, `USER devilmcp` |
| Read-only project | `:ro` mount flag |
| Isolated filesystem | Container boundary |
| No network (optional) | `network_mode: none` |
| Resource limits | Can add in compose |

### Optional: Add Resource Limits

```yaml
services:
  devilmcp:
    # ... other config
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '0.5'
          memory: 512M
```

---

## Files to Create

| File | Action |
|------|--------|
| `Dockerfile` | CREATE |
| `docker-compose.yml` | CREATE |
| `.dockerignore` | CREATE |
| `docker/entrypoint.sh` | CREATE |
| `AI_INSTRUCTIONS.md` | MODIFY - add Docker setup option |
| `README.md` | MODIFY - add Docker usage |

---

## Success Criteria

- [ ] `docker compose build` succeeds
- [ ] `docker compose up` starts server
- [ ] MCP connection works through Docker
- [ ] Data persists across container restarts
- [ ] Project directory mounted read-only
- [ ] Non-root user in container
- [ ] Health check passes
