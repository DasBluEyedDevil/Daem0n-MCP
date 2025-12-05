# Pydantic Settings Design

**Date:** 2025-12-04
**Status:** Approved
**Scope:** Replace scattered os.getenv calls with centralized Pydantic Settings

---

## Problem Statement

Current state:
- `os.getenv('STORAGE_PATH', 'default')` scattered across files
- No type validation (PORT could be non-integer)
- Typos in env var names fail silently
- No IDE autocomplete for config values

---

## Design

### Settings Class

```python
# devilmcp/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Core paths
    project_root: str = "."
    storage_path: Optional[str] = None  # Auto-detect if not set

    # Server
    port: int = 8080
    log_level: str = "INFO"

    # Timeouts (ms)
    default_command_timeout: int = 30000
    default_init_timeout: int = 10000

    # Feature flags
    auto_migrate: bool = True  # Run Alembic on startup

    class Config:
        env_prefix = "DEVILMCP_"
        env_file = ".env"
        env_file_encoding = "utf-8"

# Singleton instance
settings = Settings()
```

### Usage Pattern

```python
# Before
import os
port = int(os.getenv('PORT', 8080))
log_level = os.getenv('LOG_LEVEL', 'INFO')

# After
from devilmcp.config import settings
port = settings.port
log_level = settings.log_level
```

### Environment Variables

| Setting | Env Var | Default |
|---------|---------|---------|
| `project_root` | `DEVILMCP_PROJECT_ROOT` | `"."` |
| `storage_path` | `DEVILMCP_STORAGE_PATH` | Auto-detect |
| `port` | `DEVILMCP_PORT` | `8080` |
| `log_level` | `DEVILMCP_LOG_LEVEL` | `"INFO"` |
| `default_command_timeout` | `DEVILMCP_DEFAULT_COMMAND_TIMEOUT` | `30000` |
| `auto_migrate` | `DEVILMCP_AUTO_MIGRATE` | `True` |

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `devilmcp/config.py` | CREATE |
| `devilmcp/server.py` | MODIFY - use settings |
| `devilmcp/database.py` | MODIFY - use settings |
| `devilmcp/tool_registry.py` | MODIFY - use settings for timeouts |
| `requirements.txt` | MODIFY - add pydantic-settings>=2.0.0 |
| `.env.example` | MODIFY - update with DEVILMCP_ prefix |

---

## Dependencies

```
pydantic-settings>=2.0.0
```

---

## Success Criteria

- [ ] All os.getenv calls replaced with settings.x
- [ ] Type validation works (invalid PORT fails on startup)
- [ ] .env file loading works
- [ ] DEVILMCP_ prefix works for all settings
- [ ] IDE autocomplete works for settings
