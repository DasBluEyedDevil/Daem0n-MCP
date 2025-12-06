#!/usr/bin/env python3
"""
Migration script: Convert old DevilMCP database to new simplified schema.

This script migrates data from the old schema (13 tables) to the new schema (3 tables):
- decisions -> memories (category='decision')
- thoughts/insights -> memories (category='learning')
- cascade_events -> memories (category='warning')
- changes with issues -> memories (category='warning')

Usage:
    python scripts/migrate_to_v2.py /path/to/project/.devilmcp/storage/devilmcp.db

Or to migrate the current project:
    python scripts/migrate_to_v2.py
"""

import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime


def extract_keywords(text: str, tags: list = None) -> str:
    """Extract keywords for the new schema."""
    if not text:
        return ""

    import re
    STOP_WORDS = {
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'to', 'of',
        'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into', 'through',
        'and', 'but', 'if', 'or', 'because', 'this', 'that', 'it', 'we', 'they',
        'use', 'using', 'used'
    }

    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 2]

    if tags:
        keywords.extend([t.lower() for t in tags if isinstance(t, str)])

    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return " ".join(unique)


def migrate_database(db_path: str) -> dict:
    """
    Migrate old database to new schema.

    Returns statistics about the migration.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Create backup
    backup_path = db_path.with_suffix('.db.backup')
    if not backup_path.exists():
        import shutil
        shutil.copy(db_path, backup_path)
        print(f"Created backup: {backup_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    stats = {
        "decisions_migrated": 0,
        "thoughts_migrated": 0,
        "insights_migrated": 0,
        "cascade_events_migrated": 0,
        "changes_migrated": 0,
        "errors": []
    }

    # Check if old tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    # Check if already migrated (new tables exist)
    if 'memories' in existing_tables and 'rules' in existing_tables:
        # Check if old tables still have data
        has_old_data = False
        for table in ['decisions', 'thoughts', 'insights', 'cascade_events', 'changes']:
            if table in existing_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                if cursor.fetchone()[0] > 0:
                    has_old_data = True
                    break

        if not has_old_data:
            print("Database appears to already be migrated (new tables exist, old tables empty)")
            conn.close()
            return stats

    # Create new tables if they don't exist
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            rationale TEXT,
            context TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            keywords TEXT,
            outcome TEXT,
            worked INTEGER,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
        CREATE INDEX IF NOT EXISTS idx_memories_keywords ON memories(keywords);

        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY,
            trigger TEXT NOT NULL,
            trigger_keywords TEXT,
            must_do TEXT DEFAULT '[]',
            must_not TEXT DEFAULT '[]',
            ask_first TEXT DEFAULT '[]',
            warnings TEXT DEFAULT '[]',
            priority INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            created_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_rules_trigger_keywords ON rules(trigger_keywords);

        CREATE TABLE IF NOT EXISTS project_state (
            id INTEGER PRIMARY KEY,
            project_path TEXT UNIQUE NOT NULL,
            summary TEXT DEFAULT '{}',
            memory_count INTEGER DEFAULT 0,
            rule_count INTEGER DEFAULT 0,
            updated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_project_state_path ON project_state(project_path);
    """)

    # Migrate decisions -> memories (category='decision')
    if 'decisions' in existing_tables:
        print("Migrating decisions...")
        cursor.execute("SELECT * FROM decisions")
        for row in cursor.fetchall():
            try:
                tags = json.loads(row['tags']) if row['tags'] else []
                context = json.loads(row['context']) if row['context'] else {}

                # Add alternatives to context
                if row['alternatives_considered']:
                    alts = json.loads(row['alternatives_considered'])
                    if alts:
                        context['alternatives'] = alts

                if row['expected_impact']:
                    context['expected_impact'] = row['expected_impact']
                if row['risk_level']:
                    context['risk_level'] = row['risk_level']

                keywords = extract_keywords(row['decision'], tags)
                if row['rationale']:
                    keywords += " " + extract_keywords(row['rationale'])

                # Determine if worked based on outcome
                worked = None
                if row['outcome']:
                    outcome_lower = row['outcome'].lower()
                    if 'success' in outcome_lower or 'worked' in outcome_lower or 'good' in outcome_lower:
                        worked = 1
                    elif 'fail' in outcome_lower or 'issue' in outcome_lower or 'problem' in outcome_lower:
                        worked = 0

                cursor.execute("""
                    INSERT INTO memories (category, content, rationale, context, tags, keywords,
                                         outcome, worked, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'decision',
                    row['decision'],
                    row['rationale'],
                    json.dumps(context),
                    json.dumps(tags),
                    keywords.strip(),
                    row['outcome'] or row['actual_impact'],
                    worked,
                    row['timestamp'],
                    row['updated_at']
                ))
                stats["decisions_migrated"] += 1
            except Exception as e:
                stats["errors"].append(f"Decision {row['id']}: {e}")

    # Migrate thoughts -> memories (category='learning')
    if 'thoughts' in existing_tables:
        print("Migrating thoughts...")
        cursor.execute("SELECT * FROM thoughts WHERE confidence >= 0.7")  # Only high-confidence thoughts
        for row in cursor.fetchall():
            try:
                related = json.loads(row['related_to']) if row['related_to'] else []
                context = {
                    'original_category': row['category'],
                    'confidence': row['confidence'],
                    'related_to': related
                }
                if row['session_id']:
                    context['session_id'] = row['session_id']

                keywords = extract_keywords(row['thought'])

                cursor.execute("""
                    INSERT INTO memories (category, content, rationale, context, tags, keywords,
                                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'learning',
                    row['thought'],
                    row['reasoning'],
                    json.dumps(context),
                    json.dumps([row['category']]),
                    keywords,
                    row['timestamp'],
                    row['timestamp']
                ))
                stats["thoughts_migrated"] += 1
            except Exception as e:
                stats["errors"].append(f"Thought {row['id']}: {e}")

    # Migrate insights -> memories (category='learning')
    if 'insights' in existing_tables:
        print("Migrating insights...")
        cursor.execute("SELECT * FROM insights")
        for row in cursor.fetchall():
            try:
                context = {}
                if row['source']:
                    context['source'] = row['source']
                if row['applicability']:
                    context['applicability'] = row['applicability']
                if row['session_id']:
                    context['session_id'] = row['session_id']

                keywords = extract_keywords(row['insight'])

                cursor.execute("""
                    INSERT INTO memories (category, content, rationale, context, tags, keywords,
                                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'learning',
                    row['insight'],
                    row['applicability'],
                    json.dumps(context),
                    json.dumps([]),
                    keywords,
                    row['timestamp'],
                    row['timestamp']
                ))
                stats["insights_migrated"] += 1
            except Exception as e:
                stats["errors"].append(f"Insight {row['id']}: {e}")

    # Migrate cascade_events -> memories (category='warning')
    if 'cascade_events' in existing_tables:
        print("Migrating cascade events...")
        cursor.execute("SELECT * FROM cascade_events")
        for row in cursor.fetchall():
            try:
                affected = json.loads(row['affected_components']) if row['affected_components'] else []
                context = {
                    'trigger': row['trigger'],
                    'severity': row['severity'],
                    'affected_components': affected
                }

                content = f"CASCADE FAILURE: {row['description']}"
                if row['resolution']:
                    content += f" | Resolution: {row['resolution']}"

                keywords = extract_keywords(row['description'])
                keywords += " " + extract_keywords(row['trigger'])

                cursor.execute("""
                    INSERT INTO memories (category, content, rationale, context, tags, keywords,
                                         created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'warning',
                    content,
                    row['resolution'],
                    json.dumps(context),
                    json.dumps(['cascade', row['severity']]),
                    keywords.strip(),
                    row['timestamp'],
                    row['timestamp']
                ))
                stats["cascade_events_migrated"] += 1
            except Exception as e:
                stats["errors"].append(f"Cascade event {row['id']}: {e}")

    # Migrate problematic changes -> memories (category='warning')
    if 'changes' in existing_tables:
        print("Migrating problematic changes...")
        cursor.execute("SELECT * FROM changes WHERE status IN ('failed', 'rolled_back') OR issues_encountered != '[]'")
        for row in cursor.fetchall():
            try:
                issues = json.loads(row['issues_encountered']) if row['issues_encountered'] else []
                risk = json.loads(row['risk_assessment']) if row['risk_assessment'] else {}
                affected = json.loads(row['affected_components']) if row['affected_components'] else []

                if not issues and row['status'] not in ('failed', 'rolled_back'):
                    continue

                context = {
                    'file_path': row['file_path'],
                    'change_type': row['change_type'],
                    'status': row['status'],
                    'affected_components': affected,
                    'risk_assessment': risk
                }

                content = f"CHANGE ISSUE in {row['file_path']}: {row['description']}"
                if issues:
                    content += f" | Issues: {', '.join(issues)}"

                keywords = extract_keywords(row['description'])
                keywords += " " + extract_keywords(row['file_path'])

                cursor.execute("""
                    INSERT INTO memories (category, content, rationale, context, tags, keywords,
                                         outcome, worked, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    'warning',
                    content,
                    row['rationale'],
                    json.dumps(context),
                    json.dumps([row['change_type'], 'change-issue']),
                    keywords.strip(),
                    row['actual_impact'],
                    0,  # worked = False for problematic changes
                    row['timestamp'],
                    row['updated_at']
                ))
                stats["changes_migrated"] += 1
            except Exception as e:
                stats["errors"].append(f"Change {row['id']}: {e}")

    conn.commit()
    conn.close()

    return stats


def main():
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        # Try to find database in current project
        from pathlib import Path
        cwd = Path.cwd()
        db_path = cwd / ".devilmcp" / "storage" / "devilmcp.db"
        if not db_path.exists():
            print("Usage: python scripts/migrate_to_v2.py /path/to/devilmcp.db")
            print(f"       Or run from project root (checked: {db_path})")
            sys.exit(1)

    print(f"Migrating database: {db_path}")
    print("=" * 60)

    try:
        stats = migrate_database(db_path)

        print("\nMigration complete!")
        print("-" * 40)
        print(f"Decisions migrated: {stats['decisions_migrated']}")
        print(f"Thoughts migrated:  {stats['thoughts_migrated']}")
        print(f"Insights migrated:  {stats['insights_migrated']}")
        print(f"Cascade events:     {stats['cascade_events_migrated']}")
        print(f"Changes (issues):   {stats['changes_migrated']}")

        total = sum([
            stats['decisions_migrated'],
            stats['thoughts_migrated'],
            stats['insights_migrated'],
            stats['cascade_events_migrated'],
            stats['changes_migrated']
        ])
        print(f"\nTotal memories created: {total}")

        if stats['errors']:
            print(f"\nWarnings ({len(stats['errors'])}):")
            for err in stats['errors'][:10]:
                print(f"  - {err}")
            if len(stats['errors']) > 10:
                print(f"  ... and {len(stats['errors']) - 10} more")

        print("\nBackup saved with .backup extension")
        print("You can safely delete old tables after verifying migration")

    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
