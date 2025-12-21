"""
Daem0nMCP CLI - Command-line interface for memory checks.

Used by pre-commit hooks and direct invocation.

Usage:
    python -m daem0nmcp.cli [--json] [--project-path PATH] <command>

    python -m daem0nmcp.cli check <filepath>
    python -m daem0nmcp.cli briefing
    python -m daem0nmcp.cli scan-todos [--auto-remember] [--path PATH]
    python -m daem0nmcp.cli migrate [--backfill-vectors]

Global Options:
    --json              Output as JSON for automation/scripting
    --project-path PATH Specify project root path (sets DAEM0NMCP_PROJECT_ROOT)
"""

import sys
import os
import asyncio
import argparse
import json
from pathlib import Path

from .config import settings
from .database import DatabaseManager
from .memory import MemoryManager
from .rules import RulesEngine


async def check_file(filepath: str, db: DatabaseManager, memory: MemoryManager, rules: RulesEngine) -> dict:
    """Check a file against memories and rules."""
    await db.init_db()

    results = {
        "file": filepath,
        "warnings": [],
        "blockers": [],
        "must_do": [],
        "must_not": []
    }

    # Get file-specific memories
    file_memories = await memory.recall_for_file(filepath)

    # Check for warnings in file memories
    for cat in ['warnings', 'decisions', 'patterns', 'learnings']:
        for mem in file_memories.get(cat, []):
            if mem.get('worked') is False:
                results["warnings"].append({
                    "type": "FAILED_APPROACH",
                    "content": mem['content'],
                    "outcome": mem.get('outcome')
                })
            elif cat == 'warnings':
                results["warnings"].append({
                    "type": "WARNING",
                    "content": mem['content']
                })

    # Check rules based on filename
    filename = Path(filepath).name
    rule_check = await rules.check_rules(f"modifying {filename}")

    if rule_check.get('guidance'):
        guidance = rule_check['guidance']
        results["must_do"] = guidance.get('must_do', [])
        results["must_not"] = guidance.get('must_not', [])

        # Rule warnings become blockers if high priority
        for warning in guidance.get('warnings', []):
            results["warnings"].append({
                "type": "RULE_WARNING",
                "content": warning
            })

    return results


async def get_briefing(db: DatabaseManager, memory: MemoryManager) -> dict:
    """Get session briefing."""
    await db.init_db()
    return await memory.get_statistics()


def format_check_result(result: dict) -> str:
    """Format check result for CLI output."""
    lines = []

    if result["warnings"]:
        for w in result["warnings"]:
            lines.append(f"WARNING [{w['type']}]: {w['content']}")
            if w.get('outcome'):
                lines.append(f"  Outcome: {w['outcome']}")

    if result["must_do"]:
        lines.append("MUST DO:")
        for item in result["must_do"]:
            lines.append(f"  - {item}")

    if result["must_not"]:
        lines.append("MUST NOT:")
        for item in result["must_not"]:
            lines.append(f"  - {item}")

    if not lines:
        lines.append("OK: No concerns found")

    return "\n".join(lines)


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Daem0nMCP CLI")

    # Global options
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--project-path", help="Project root path")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # check command
    check_parser = subparsers.add_parser("check", help="Check a file against memory")
    check_parser.add_argument("filepath", help="File to check")

    # briefing command
    subparsers.add_parser("briefing", help="Get session briefing")

    # scan-todos command
    scan_parser = subparsers.add_parser("scan-todos", help="Scan for TODO/FIXME comments")
    scan_parser.add_argument("--auto-remember", action="store_true", help="Auto-create warnings")
    scan_parser.add_argument("--path", help="Path to scan", default=".")

    # migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations")
    migrate_parser.add_argument("--backfill-vectors", action="store_true",
                                help="Backfill vector embeddings for existing memories")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Set project path if provided
    if args.project_path:
        os.environ['DAEM0NMCP_PROJECT_ROOT'] = args.project_path

    # Initialize components
    storage_path = settings.get_storage_path()
    db = DatabaseManager(storage_path)
    memory = MemoryManager(db)
    rules = RulesEngine(db)

    if args.command == "check":
        result = asyncio.run(check_file(args.filepath, db, memory, rules))
        if args.json:
            print(json.dumps(result, default=str))
        else:
            print(format_check_result(result))

    elif args.command == "briefing":
        result = asyncio.run(get_briefing(db, memory))
        if args.json:
            print(json.dumps(result, default=str))
        else:
            print(f"Total memories: {result.get('total_memories', 0)}")
            print(f"By category: {result.get('by_category', {})}")
            if result.get('learning_insights', {}).get('suggestion'):
                print(f"Suggestion: {result['learning_insights']['suggestion']}")

    elif args.command == "scan-todos":
        # Import here to avoid circular imports
        from .server import _scan_for_todos

        todos = _scan_for_todos(args.path)
        if args.json:
            result = {
                "total": len(todos),
                "todos": todos
            }
            print(json.dumps(result, default=str))
        else:
            print(f"Found {len(todos)} TODO/FIXME items:")
            for todo in todos[:20]:  # Limit output
                print(f"  [{todo['type']}] {todo['file']}:{todo['line']} - {todo['content'][:60]}")
            if len(todos) > 20:
                print(f"  ... and {len(todos) - 20} more")

    elif args.command == "migrate":
        from .migrations import run_migrations, migrate_and_backfill_vectors

        db_path = str(Path(storage_path) / "daem0nmcp.db")

        if args.backfill_vectors:
            result = migrate_and_backfill_vectors(db_path)
            if args.json:
                result['database'] = db_path
                print(json.dumps(result, default=str))
            else:
                print(f"Database: {db_path}")
                print(f"\nMigration complete:")
                print(f"  Schema migrations: {result['schema_migrations']}")
                for m in result.get('applied', []):
                    print(f"    - {m}")
                print(f"  Vectors backfilled: {result['vectors_backfilled']}")
                print(f"  Vectors available: {result['vectors_available']}")
                print(f"\n{result['message']}")
        else:
            count, applied = run_migrations(db_path)
            if args.json:
                result = {
                    "database": db_path,
                    "schema_migrations": count,
                    "applied": applied,
                    "up_to_date": count == 0
                }
                print(json.dumps(result, default=str))
            else:
                print(f"Database: {db_path}")
                print(f"\nSchema migrations applied: {count}")
                for m in applied:
                    print(f"  - {m}")
                if count == 0:
                    print("Database is up to date.")
                print("\nTo also backfill vectors, run: python -m daem0nmcp.cli migrate --backfill-vectors")


if __name__ == "__main__":
    main()
