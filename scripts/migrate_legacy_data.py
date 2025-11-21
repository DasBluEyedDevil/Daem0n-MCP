import asyncio
import json
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import modules
sys.path.append(str(Path(__file__).parent.parent))

from database import DatabaseManager
from models import Decision

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_decisions(db_manager: DatabaseManager, json_path: Path):
    """Migrate decisions from JSON to SQLite."""
    if not json_path.exists():
        logger.warning(f"No legacy decisions found at {json_path}")
        return

    logger.info(f"Reading legacy decisions from {json_path}")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            decisions_data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read JSON file: {e}")
        return

    count = 0
    async with db_manager.get_session() as session:
        for item in decisions_data:
            # Parse timestamp
            try:
                # Handle ISO format "2025-11-12T20:59:39.681545"
                timestamp = datetime.fromisoformat(item.get("timestamp"))
            except (ValueError, TypeError):
                timestamp = datetime.now()

            # Create Decision object
            decision = Decision(
                # We intentionally let DB assign new IDs to avoid conflicts, 
                # unless you want to preserve exact IDs. Here we map content.
                decision=item.get("decision", ""),
                rationale=item.get("rationale", ""),
                context=item.get("context", {}),
                alternatives_considered=item.get("alternatives_considered", []),
                expected_impact=item.get("expected_impact"),
                risk_level=item.get("risk_level", "medium"),
                tags=item.get("tags", []),
                timestamp=timestamp,
                outcome=item.get("outcome"),
                actual_impact=item.get("actual_impact"),
                lessons_learned=item.get("lessons_learned")
            )
            session.add(decision)
            count += 1
        
        await session.commit()
    
    logger.info(f"Successfully migrated {count} decisions.")

async def main():
    # Determine paths
    project_root = Path(os.getcwd())
    storage_path = project_root / ".devilmcp" / "storage"
    legacy_decisions = storage_path / "decisions.json"
    
    # Initialize DB Manager (this points to the NEW db location)
    # Ensure this matches your server.py configuration
    # If server.py uses .devilmcp/storage for the DB, we are good.
    db_manager = DatabaseManager(str(storage_path))
    
    logger.info("Starting migration...")
    await db_manager.init_db()
    
    await migrate_decisions(db_manager, legacy_decisions)
    
    logger.info("Migration complete.")

if __name__ == "__main__":
    asyncio.run(main())
