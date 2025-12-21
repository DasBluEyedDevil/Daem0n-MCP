"""
Database migrations for Daem0nMCP.

Handles schema updates for existing databases.
"""

import sqlite3
import logging
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Migration definitions: (version, description, sql_statements)
MIGRATIONS: List[Tuple[int, str, List[str]]] = [
    (1, "Add vector_embedding column", [
        """
        ALTER TABLE memories ADD COLUMN vector_embedding BLOB;
        """
    ]),
    (2, "Create FTS5 virtual table for full-text search", [
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
            content,
            rationale,
            tags,
            content='memories',
            content_rowid='id'
        );
        """,
        """
        INSERT OR IGNORE INTO memories_fts(rowid, content, rationale, tags)
        SELECT
            id,
            content,
            COALESCE(rationale, ''),
            COALESCE((SELECT group_concat(value, ' ') FROM json_each(tags)), '')
        FROM memories;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
            INSERT INTO memories_fts(rowid, content, rationale, tags)
            SELECT new.id, new.content, COALESCE(new.rationale, ''),
                   COALESCE((SELECT group_concat(value, ' ') FROM json_each(new.tags)), '');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, rationale, tags)
            SELECT 'delete', old.id, old.content, COALESCE(old.rationale, ''),
                   COALESCE((SELECT group_concat(value, ' ') FROM json_each(old.tags)), '');
        END;
        """,
        """
        CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
            INSERT INTO memories_fts(memories_fts, rowid, content, rationale, tags)
            SELECT 'delete', old.id, old.content, COALESCE(old.rationale, ''),
                   COALESCE((SELECT group_concat(value, ' ') FROM json_each(old.tags)), '');
            INSERT INTO memories_fts(rowid, content, rationale, tags)
            SELECT new.id, new.content, COALESCE(new.rationale, ''),
                   COALESCE((SELECT group_concat(value, ' ') FROM json_each(new.tags)), '');
        END;
        """
    ]),
    (3, "Add pinned and archived columns to memories", [
        "ALTER TABLE memories ADD COLUMN pinned BOOLEAN DEFAULT 0;",
        "ALTER TABLE memories ADD COLUMN archived BOOLEAN DEFAULT 0;"
    ]),
]


def get_current_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from database."""
    cursor = conn.cursor()

    # Check if version table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='schema_version'
    """)

    if not cursor.fetchone():
        # Create version table
        cursor.execute("""
            CREATE TABLE schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        return 0

    cursor.execute("SELECT MAX(version) FROM schema_version")
    result = cursor.fetchone()
    return result[0] if result[0] else 0


def check_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def run_migrations(db_path: str) -> Tuple[int, List[str]]:
    """
    Run all pending migrations on the database.

    Args:
        db_path: Path to the SQLite database

    Returns:
        Tuple of (migrations_run, list of descriptions)
    """
    if not Path(db_path).exists():
        return 0, ["Database does not exist yet - will be created fresh"]

    conn = sqlite3.Connection(db_path)
    applied = []

    try:
        current_version = get_current_version(conn)

        for version, description, statements in MIGRATIONS:
            if version <= current_version:
                continue

            logger.info(f"Applying migration {version}: {description}")

            for sql in statements:
                sql = sql.strip()
                if not sql:
                    continue

                # Handle ALTER TABLE ADD COLUMN - check if column exists first
                if "ALTER TABLE" in sql and "ADD COLUMN" in sql:
                    # Parse table and column names
                    parts = sql.split()
                    table_idx = parts.index("TABLE") + 1
                    column_idx = parts.index("COLUMN") + 1
                    table = parts[table_idx]
                    column = parts[column_idx]

                    if check_column_exists(conn, table, column):
                        logger.info(f"  Column {column} already exists in {table}, skipping")
                        continue

                try:
                    conn.execute(sql)
                except sqlite3.OperationalError as e:
                    # Ignore "duplicate column" errors
                    if "duplicate column" in str(e).lower():
                        logger.info(f"  Column already exists, skipping")
                        continue
                    raise

            # Record migration
            conn.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (version,)
            )
            conn.commit()
            applied.append(f"v{version}: {description}")

    finally:
        conn.close()

    return len(applied), applied


def migrate_and_backfill_vectors(db_path: str) -> dict:
    """
    Run migrations and optionally backfill vector embeddings for existing memories.

    Args:
        db_path: Path to the SQLite database

    Returns:
        Migration report
    """
    from . import vectors

    # First run schema migrations
    count, applied = run_migrations(db_path)

    result = {
        "schema_migrations": count,
        "applied": applied,
        "vectors_backfilled": 0,
        "vectors_available": vectors.is_available()
    }

    if not vectors.is_available():
        result["message"] = (
            f"Schema updated ({count} migrations). "
            "Vector backfill skipped - install sentence-transformers for vectors."
        )
        return result

    # Backfill vectors for memories that don't have them
    conn = sqlite3.Connection(db_path)
    try:
        cursor = conn.cursor()

        # Find memories without vectors
        cursor.execute("""
            SELECT id, content, rationale
            FROM memories
            WHERE vector_embedding IS NULL
        """)

        memories = cursor.fetchall()

        if not memories:
            result["message"] = f"Schema updated ({count} migrations). All memories already have vectors."
            return result

        logger.info(f"Backfilling vectors for {len(memories)} memories...")

        for mem_id, content, rationale in memories:
            text = content
            if rationale:
                text += " " + rationale

            embedding = vectors.encode(text)
            if embedding:
                cursor.execute(
                    "UPDATE memories SET vector_embedding = ? WHERE id = ?",
                    (embedding, mem_id)
                )
                result["vectors_backfilled"] += 1

        conn.commit()

        result["message"] = (
            f"Schema updated ({count} migrations). "
            f"Backfilled vectors for {result['vectors_backfilled']} memories."
        )

    finally:
        conn.close()

    return result


# CLI entry point
def main():
    """Run migrations from command line."""
    import sys
    from .config import settings

    db_path = str(settings.get_storage_path())
    print(f"Migrating database: {db_path}")

    result = migrate_and_backfill_vectors(db_path)

    print(f"\nMigration complete:")
    print(f"  Schema migrations: {result['schema_migrations']}")
    for m in result.get('applied', []):
        print(f"    - {m}")
    print(f"  Vectors backfilled: {result['vectors_backfilled']}")
    print(f"  Vectors available: {result['vectors_available']}")
    print(f"\n{result['message']}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
