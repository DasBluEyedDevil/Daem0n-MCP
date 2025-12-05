# Alembic Migrations Design

**Date:** 2025-12-04
**Status:** Approved
**Scope:** Replace manual migration scripts with Alembic for SQLite schema management

---

## Problem Statement

Current state:
- Manual script `scripts/migrate_db_indexes.py` for schema changes
- No versioning of database schema
- Risk of data loss as schema evolves
- No rollback capability

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migration tool | Alembic | Standard for SQLAlchemy, auto-generates migrations |
| JSON migration | Deprecate | SQLite is v2, users should have migrated by now |
| Auto-upgrade | Yes, on startup | Zero user action required |
| Package location | Inside `devilmcp/` | Ships with pip install |

---

## Project Structure

```
devilmcp/
├── alembic/
│   ├── env.py              # Migration environment config
│   ├── script.py.mako      # Template for new migrations
│   └── versions/           # Auto-generated migration scripts
│       └── 001_initial_schema.py
├── alembic.ini             # Alembic configuration (in package)
├── database.py             # Modified - add auto-upgrade
└── models.py               # Unchanged - source of truth
```

---

## Implementation Details

### env.py - Dynamic Database URL

```python
# devilmcp/alembic/env.py
import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from devilmcp.models import Base
from devilmcp.database import get_database_url

config = context.config
config.set_main_option("sqlalchemy.url", get_database_url())
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

### Auto-Upgrade on Startup

```python
# In DatabaseManager.initialize()
async def initialize(self):
    from alembic.config import Config
    from alembic import command

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", "devilmcp:alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", self.database_url)

    command.upgrade(alembic_cfg, "head")

    # Then create engine and session as before...
```

### Initial Migration (Baseline)

```python
# devilmcp/alembic/versions/001_initial_schema.py
"""Initial schema - captures existing 16 tables"""
from alembic import op
import sqlalchemy as sa

revision = '001'
down_revision = None

def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Only create if doesn't exist (idempotent for existing DBs)
    if 'decisions' not in existing_tables:
        op.create_table('decisions', ...)

    if 'tasks' not in existing_tables:
        op.create_table('tasks', ...)

    # ... all 16 tables

def downgrade():
    op.drop_table('external_dependencies')
    op.drop_table('file_dependencies')
    # ... all tables in reverse order
```

---

## Developer Workflow

### Making Schema Changes

```bash
# 1. Modify models.py
# 2. Auto-generate migration
alembic revision --autogenerate -m "add priority to tasks"

# 3. Review generated migration
# 4. Test locally
alembic upgrade head

# 5. Commit models.py + migration file
```

### CLI Commands

```bash
devilmcp db version    # Show current schema version
devilmcp db upgrade    # Manually run migrations
devilmcp db status     # Show pending migrations
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `devilmcp/alembic/__init__.py` | CREATE |
| `devilmcp/alembic/env.py` | CREATE |
| `devilmcp/alembic/script.py.mako` | CREATE |
| `devilmcp/alembic/versions/001_initial_schema.py` | CREATE |
| `devilmcp/alembic.ini` | CREATE |
| `devilmcp/database.py` | MODIFY - add get_database_url(), auto-upgrade |
| `requirements.txt` | MODIFY - add alembic>=1.13.0 |
| `scripts/migrate_db_indexes.py` | DELETE |
| `scripts/migrate_json_to_sqlite.py` | DELETE (if exists) |
| `README.md` | MODIFY - update migration docs |

---

## Dependencies

```
alembic>=1.13.0
```

---

## Migration Path

### For Existing Users
1. Server starts, runs `alembic upgrade head`
2. Initial migration detects existing tables, skips creation
3. Future migrations apply incrementally

### For New Users
1. Server starts, runs `alembic upgrade head`
2. All migrations apply in order, creating fresh schema

---

## Success Criteria

- [ ] `alembic upgrade head` works on fresh database
- [ ] `alembic upgrade head` works on existing database (no-op for baseline)
- [ ] Auto-upgrade runs on server startup
- [ ] `alembic revision --autogenerate` detects model changes
- [ ] CLI commands work (`devilmcp db version/upgrade/status`)
- [ ] Old migration scripts deleted
