"""
Process Manager Module
Handles spawning, monitoring, and managing CLI tool processes.
"""

import asyncio
import logging
import uuid
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from .database import DatabaseManager
from .models import Tool, ToolSession 
from sqlalchemy import select

logger = logging.getLogger(__name__)

class ProcessState(Enum):
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    TERMINATED = "terminated"

@dataclass
class ProcessInfo:
    """Information about a running CLI process"""
    tool_name: str
    session_id: str # This is the ToolSession.session_id (UUID)
    tool_db_id: int # This is the Tool.id from DB
    pid: int
    state: ProcessState
    started_at: datetime
    last_activity: datetime
    command: str
    stdin_writer: asyncio.StreamWriter
    stdout_reader: asyncio.StreamReader
    stderr_reader: asyncio.StreamReader
    process_obj: asyncio.subprocess.Process # Keep a reference to the process object

class ProcessManager:
    """Manages lifecycle of CLI tool processes"""
    
    def __init__(self, db_manager: DatabaseManager): # Added db_manager
        self.db = db_manager
        self.processes: Dict[str, ProcessInfo] = {} # Keyed by tool_name
        self._lock = asyncio.Lock()
    
    async def spawn_process(
        self,
        tool_name: str,
        command: str,
        args: List[str],
        env: Optional[Dict[str, str]] = None,
    ) -> ProcessInfo:
        """Spawn a new CLI tool process"""
        logger.info(f"Spawning process for {tool_name}")
        
        # Build command
        full_command = [command] + args
        
        # Generate a unique session ID
        session_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        # Get tool_id from DB
        tool_db_id = None
        async with self.db.get_session() as session:
            tool_record = await session.execute(select(Tool).where(Tool.name == tool_name))
            tool_record = tool_record.scalar_one_or_none()
            if tool_record:
                tool_db_id = tool_record.id
            else:
                raise ValueError(f"Tool '{tool_name}' not found in database. Please register it first.")

        # Create ToolSession record in DB
        new_tool_session = ToolSession(
            tool_id=tool_db_id,
            session_id=session_uuid,
            state=ProcessState.INITIALIZING.value,
            started_at=now,
            last_activity=now,
            context={"command": " ".join(full_command)}
        )
        async with self.db.get_session() as session:
            session.add(new_tool_session)
            await session.commit()
            await session.refresh(new_tool_session) # Get assigned ID

        # Spawn process
        process = await asyncio.create_subprocess_exec(
            *full_command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        # Create process info
        proc_info = ProcessInfo(
            tool_name=tool_name,
            session_id=session_uuid,
            tool_db_id=tool_db_id,
            pid=process.pid,
            state=ProcessState.INITIALIZING,
            started_at=now,
            last_activity=now,
            command=command,
            stdin_writer=process.stdin,
            stdout_reader=process.stdout,
            stderr_reader=process.stderr,
            process_obj=process
        )
        
        async with self._lock:
            self.processes[tool_name] = proc_info # Use tool_name as key for simplicity, assuming one session per tool type for now
        
        # Update ToolSession with PID
        async with self.db.get_session() as session:
            db_session_record = await session.execute(select(ToolSession).where(ToolSession.session_id == session_uuid))
            db_session_record = db_session_record.scalar_one_or_none()
            if db_session_record:
                db_session_record.pid = process.pid
                await session.commit()
        
        return proc_info
    
    async def send_command(
        self,
        tool_name: str,
        command: str,
        timeout: float = 30.0,
        prompt_patterns: Optional[List[str]] = None
    ) -> str:
        """Send command to a CLI tool and get response"""
        proc_info = self.processes.get(tool_name)
        if not proc_info:
            raise ValueError(f"No process found for tool: {tool_name}")
        
        # Update state
        proc_info.state = ProcessState.BUSY
        proc_info.last_activity = datetime.now(timezone.utc)

        # Update ToolSession in DB
        async with self.db.get_session() as session:
            db_session_record = await session.execute(select(ToolSession).where(ToolSession.session_id == proc_info.session_id))
            db_session_record = db_session_record.scalar_one_or_none()
            if db_session_record:
                db_session_record.state = ProcessState.BUSY.value
                db_session_record.last_activity = proc_info.last_activity
                await session.commit()
        
        # Send command
        try:
            proc_info.stdin_writer.write(f"{command}\n".encode())
            await proc_info.stdin_writer.drain()
        except (ConnectionResetError, BrokenPipeError) as e:
            # Process might have exited or closed stdin, but might still have output buffered
            logger.warning(f"Write failed for {tool_name}: {e}. Attempting to read stdout anyway.")
        
        # Read response until a prompt pattern is matched or timeout
        response_lines = []
        try:
            while True:
                line = await asyncio.wait_for(
                    proc_info.stdout_reader.readline(),
                    timeout=timeout
                )
                if not line: # EOF
                    break
                decoded_line = line.decode(errors='ignore').strip()
                response_lines.append(decoded_line)

                # Check for prompt patterns
                if prompt_patterns:
                    for pattern in prompt_patterns:
                        if decoded_line.endswith(pattern):
                            break # Found prompt, stop reading
                    else:
                        continue # No prompt found, read next line
                    break # Prompt found, stop reading outer loop
                
            proc_info.state = ProcessState.READY

            # Update ToolSession in DB
            async with self.db.get_session() as session:
                db_session_record = await session.execute(select(ToolSession).where(ToolSession.session_id == proc_info.session_id))
                db_session_record = db_session_record.scalar_one_or_none()
                if db_session_record:
                    db_session_record.state = ProcessState.READY.value
                    await session.commit()

            return "\n".join(response_lines)
        except asyncio.TimeoutError:
            logger.error(f"Command timeout for {tool_name}")
            proc_info.state = ProcessState.ERROR
            async with self.db.get_session() as session:
                db_session_record = await session.execute(select(ToolSession).where(ToolSession.session_id == proc_info.session_id))
                db_session_record = db_session_record.scalar_one_or_none()
                if db_session_record:
                    db_session_record.state = ProcessState.ERROR.value
                    await session.commit()
            raise
        except Exception as e:
            logger.error(f"Error reading from {tool_name}: {e}")
            proc_info.state = ProcessState.ERROR
            async with self.db.get_session() as session:
                db_session_record = await session.execute(select(ToolSession).where(ToolSession.session_id == proc_info.session_id))
                db_session_record = db_session_record.scalar_one_or_none()
                if db_session_record:
                    db_session_record.state = ProcessState.ERROR.value
                    await session.commit()
            raise
    
    async def terminate_process(self, tool_name: str):
        """Terminate a CLI tool process"""
        proc_info = self.processes.get(tool_name)
        if not proc_info:
            return
        
        logger.info(f"Terminating process for {tool_name} (PID: {proc_info.pid})")
        
        try:
            # Send Ctrl+C equivalent (SIGINT)
            if proc_info.process_obj.returncode is None: # Still running
                proc_info.process_obj.send_signal(asyncio.subprocess.signal.SIGINT)
                await asyncio.wait_for(proc_info.process_obj.wait(), timeout=5)
            
            if proc_info.process_obj.returncode is None: # Still running after SIGINT
                proc_info.process_obj.terminate() # SIGTERM
                await asyncio.wait_for(proc_info.process_obj.wait(), timeout=5)

            if proc_info.process_obj.returncode is None: # Still running after SIGTERM
                proc_info.process_obj.kill() # SIGKILL
                await asyncio.wait_for(proc_info.process_obj.wait(), timeout=5)

        except (asyncio.TimeoutError, Exception) as e:
            logger.error(f"Error terminating {tool_name} (PID: {proc_info.pid}): {e}")
        finally:
            if proc_info.stdin_writer and not proc_info.stdin_writer.is_closing():
                proc_info.stdin_writer.close()
                await proc_info.stdin_writer.wait_closed()
            if proc_info.stdout_reader:
                proc_info.stdout_reader.feed_eof()
            if proc_info.stderr_reader:
                proc_info.stderr_reader.feed_eof()
            
            async with self._lock:
                if tool_name in self.processes:
                    del self.processes[tool_name]
            
            proc_info.state = ProcessState.TERMINATED

            # Update ToolSession in DB
            async with self.db.get_session() as session:
                db_session_record = await session.execute(select(ToolSession).where(ToolSession.session_id == proc_info.session_id))
                db_session_record = db_session_record.scalar_one_or_none()
                if db_session_record:
                    db_session_record.state = ProcessState.TERMINATED.value
                    db_session_record.ended_at = datetime.now(timezone.utc)
                    await session.commit()
    
    def get_process_status(self, tool_name: str) -> Optional[Dict]:
        """Get status of a CLI tool process"""
        proc_info = self.processes.get(tool_name)
        if not proc_info:
            return None
        
        # Check if process is still running
        if proc_info.process_obj.returncode is not None:
            proc_info.state = ProcessState.TERMINATED
        
        return {
            "tool_name": tool_name,
            "session_id": proc_info.session_id,
            "pid": proc_info.pid,
            "state": proc_info.state.value,
            "uptime_seconds": (datetime.now(timezone.utc) - proc_info.started_at).total_seconds(),
            "last_activity_seconds_ago": (datetime.now(timezone.utc) - proc_info.last_activity).total_seconds(),
            "command": proc_info.command
        }