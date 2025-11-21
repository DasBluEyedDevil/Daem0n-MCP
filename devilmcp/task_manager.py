import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from .database import DatabaseManager
from .models import Task

logger = logging.getLogger(__name__)

class TaskManager:
    """Manages project tasks and workflows."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def create_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        assigned_to: Optional[str] = None,
        tags: Optional[List[str]] = None,
        parent_id: Optional[int] = None
    ) -> Dict:
        """Create a new task."""
        async with self.db.get_session() as session:
            task = Task(
                title=title,
                description=description,
                priority=priority,
                assigned_to=assigned_to,
                tags=tags or [],
                parent_id=parent_id,
                status="todo"
            )
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return self._task_to_dict(task)

    async def update_task(
        self,
        task_id: int,
        status: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Optional[Dict]:
        """Update an existing task."""
        async with self.db.get_session() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            
            if not task:
                return None
            
            if status:
                task.status = status
                if status == "done" and not task.completed_at:
                    task.completed_at = datetime.now(timezone.utc)
                elif status != "done":
                    task.completed_at = None
            
            if title: task.title = title
            if description: task.description = description
            if priority: task.priority = priority
            if assigned_to: task.assigned_to = assigned_to
            if tags is not None: task.tags = tags
            
            await session.commit()
            await session.refresh(task)
            return self._task_to_dict(task)

    async def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List tasks with filters."""
        async with self.db.get_session() as session:
            stmt = select(Task)
            if status:
                stmt = stmt.where(Task.status == status)
            if priority:
                stmt = stmt.where(Task.priority == priority)
            if assigned_to:
                stmt = stmt.where(Task.assigned_to == assigned_to)
            
            stmt = stmt.order_by(Task.created_at.desc()).limit(limit)
            result = await session.execute(stmt)
            tasks = result.scalars().all()
            return [self._task_to_dict(t) for t in tasks]

    async def get_task(self, task_id: int) -> Optional[Dict]:
        """Get a specific task by ID."""
        async with self.db.get_session() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            return self._task_to_dict(task) if task else None

    async def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        async with self.db.get_session() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one_or_none()
            if task:
                await session.delete(task)
                return True
            return False

    def _task_to_dict(self, task: Task) -> Dict:
        """Convert Task model to dictionary."""
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "assigned_to": task.assigned_to,
            "tags": task.tags,
            "parent_id": task.parent_id,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }
