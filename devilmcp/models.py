from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Float, ForeignKey
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone

class Base(DeclarativeBase):
    pass

class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, index=True)
    decision = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    context = Column(JSON, default=dict)
    alternatives_considered = Column(JSON, default=list)
    expected_impact = Column(Text, nullable=True)
    risk_level = Column(String, default="medium")
    tags = Column(JSON, default=list)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    outcome = Column(Text, nullable=True)
    actual_impact = Column(Text, nullable=True)
    lessons_learned = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ThoughtSession(Base):
    __tablename__ = "thought_sessions"
    
    id = Column(String, primary_key=True)
    context = Column(JSON, default=dict)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    summary = Column(Text, nullable=True)
    outcomes = Column(JSON, default=list)
    status = Column(String, default="active")
    
class Thought(Base):
    __tablename__ = "thoughts"

    id = Column(Integer, primary_key=True, index=True)
    thought = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    reasoning = Column(Text, nullable=True)
    related_to = Column(JSON, default=list)
    confidence = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = Column(String, ForeignKey("thought_sessions.id"), nullable=True)

class Insight(Base):
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    insight = Column(Text, nullable=False)
    source = Column(String, nullable=True)
    applicability = Column(Text, nullable=True)
    session_id = Column(String, ForeignKey("thought_sessions.id"), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Change(Base):
    __tablename__ = "changes"

    id = Column(Integer, primary_key=True, index=True)
    hash = Column(String, nullable=True)
    file_path = Column(String, nullable=False)
    change_type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    affected_components = Column(JSON, default=list)
    risk_assessment = Column(JSON, default=dict)
    rollback_plan = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="planned")
    actual_impact = Column(Text, nullable=True)
    issues_encountered = Column(JSON, default=list)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class CascadeEvent(Base):
    __tablename__ = "cascade_events"

    id = Column(Integer, primary_key=True, index=True)
    trigger = Column(String, nullable=False)
    affected_components = Column(JSON, default=list)
    severity = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    resolution = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Tool(Base):
    """CLI Tool configuration"""
    __tablename__ = "tools"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    command = Column(String, nullable=False)
    args = Column(JSON, default=list)
    capabilities = Column(JSON, default=list)
    enabled = Column(Integer, default=1)  # SQLite doesn't have boolean
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used = Column(DateTime, nullable=True)

class ToolSession(Base):
    """Active CLI tool sessions"""
    __tablename__ = "tool_sessions"
    
    id = Column(Integer, primary_key=True)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    session_id = Column(String, unique=True, nullable=False, index=True) # UUID for session
    pid = Column(Integer, nullable=True)
    state = Column(String, default="idle")
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    context = Column(JSON, default=dict)

class TaskExecution(Base):
    """Record of delegated tasks"""
    __tablename__ = "task_executions"
    
    id = Column(Integer, primary_key=True)
    task_description = Column(Text, nullable=False)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    session_id = Column(String, ForeignKey("tool_sessions.session_id"), nullable=False)
    command_sent = Column(Text, nullable=False)
    response_received = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    context = Column(JSON, default=dict)

class WorkflowExecution(Base):
    """Multi-tool workflow execution tracking"""
    __tablename__ = "workflow_executions"
    
    id = Column(Integer, primary_key=True)
    workflow_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, default=list)  # List of task_execution_ids (UUIDs)
    status = Column(String, default="pending")
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, default=dict)

class Task(Base):
    """General purpose task tracking"""
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="todo") # todo, in_progress, done, blocked
    priority = Column(String, default="medium")
    assigned_to = Column(String, nullable=True) # specific tool or 'user'
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    parent_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)

class ProjectFile(Base):
    """Tracked file in the project"""
    __tablename__ = "project_files"
    
    id = Column(Integer, primary_key=True)
    file_path = Column(String, unique=True, nullable=False, index=True)
    file_type = Column(String, nullable=True)
    size = Column(Integer, nullable=True)
    last_modified = Column(DateTime, nullable=True)
    line_count = Column(Integer, nullable=True)
    hash = Column(String, nullable=True)
    language = Column(String, nullable=True)
    
class FileDependency(Base):
    """Dependencies between files"""
    __tablename__ = "file_dependencies"
    
    id = Column(Integer, primary_key=True)
    source_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=False)
    target_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=False)
    dependency_type = Column(String, default="import") # import, inheritance, usage
    
    # We might want to store external dependencies too, but for now let's link internal files
    # For external deps, we could have a separate table or just a JSON list in ProjectFile
    
class ExternalDependency(Base):
    """External package dependencies"""
    __tablename__ = "external_dependencies"
    
    id = Column(Integer, primary_key=True)
    source_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=False)
    package_name = Column(String, nullable=False)
    version_constraint = Column(String, nullable=True)
