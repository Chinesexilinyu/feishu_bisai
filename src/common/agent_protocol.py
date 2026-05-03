#!/usr/bin/env python3
from enum import Enum
from typing import Optional, Dict, Any, List
import uuid
import time

class AgentRole(str, Enum):
    DOC_AGENT = "doc_agent"
    DATA_AGENT = "data_agent"
    WEB_AGENT = "web_agent"
    HUMAN = "human"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"

class ErrorCode(str, Enum):
    SUCCESS = "0"
    PARAM_INVALID = "40001"
    TOKEN_EXPIRED = "40101"
    TOKEN_INVALID = "40102"
    PERMISSION_DENIED = "40301"
    DELEGATION_NOT_ALLOWED = "40302"
    RESOURCE_NOT_FOUND = "40401"
    CAPABILITY_NOT_SUPPORTED = "50101"
    AGENT_UNAVAILABLE = "50301"
    EXECUTION_FAILED = "50001"
    TIMEOUT = "50401"

class TaskRequest:
    def __init__(
        self,
        task_type: str,
        intent: str,
        parameters: Dict[str, Any],
        parent_task_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        timeout: int = 300
    ):
        self.task_id = str(uuid.uuid4())
        self.task_type = task_type
        self.intent = intent
        self.parameters = parameters
        self.parent_task_id = parent_task_id
        self.trace_id = trace_id or str(uuid.uuid4())
        self.context = context or {}
        self.created_at = int(time.time())
        self.timeout = timeout
        self.status = TaskStatus.PENDING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "intent": self.intent,
            "parameters": self.parameters,
            "parent_task_id": self.parent_task_id,
            "trace_id": self.trace_id,
            "context": self.context,
            "created_at": self.created_at,
            "timeout": self.timeout,
            "status": self.status.value
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRequest":
        task = cls(
            task_type=data["task_type"],
            intent=data["intent"],
            parameters=data["parameters"],
            parent_task_id=data.get("parent_task_id"),
            trace_id=data.get("trace_id"),
            context=data.get("context", {}),
            timeout=data.get("timeout", 300)
        )
        task.task_id = data.get("task_id", task.task_id)
        task.created_at = data.get("created_at", task.created_at)
        task.status = TaskStatus(data.get("status", TaskStatus.PENDING.value))
        return task

class TaskResponse:
    def __init__(
        self,
        task_id: str,
        status: TaskStatus,
        data: Optional[Dict[str, Any]] = None,
        error_code: ErrorCode = ErrorCode.SUCCESS,
        error_message: Optional[str] = None,
        trace_id: Optional[str] = None
    ):
        self.task_id = task_id
        self.status = status
        self.data = data or {}
        self.error_code = error_code
        self.error_message = error_message
        self.trace_id = trace_id
        self.completed_at = int(time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "data": self.data,
            "code": self.error_code.value,
            "message": self.error_message,
            "trace_id": self.trace_id,
            "completed_at": self.completed_at
        }

    @classmethod
    def success(
        cls,
        task_id: str,
        data: Dict[str, Any],
        trace_id: Optional[str] = None
    ) -> "TaskResponse":
        return cls(
            task_id=task_id,
            status=TaskStatus.COMPLETED,
            data=data,
            error_code=ErrorCode.SUCCESS,
            trace_id=trace_id
        )

    @classmethod
    def failed(
        cls,
        task_id: str,
        error_code: ErrorCode,
        error_message: str,
        trace_id: Optional[str] = None
    ) -> "TaskResponse":
        return cls(
            task_id=task_id,
            status=TaskStatus.FAILED,
            error_code=error_code,
            error_message=error_message,
            trace_id=trace_id
        )

    @classmethod
    def rejected(
        cls,
        task_id: str,
        error_code: ErrorCode,
        error_message: str,
        trace_id: Optional[str] = None
    ) -> "TaskResponse":
        return cls(
            task_id=task_id,
            status=TaskStatus.REJECTED,
            error_code=error_code,
            error_message=error_message,
            trace_id=trace_id
        )

class TaskDependency:
    def __init__(
        self,
        task_id: str,
        depends_on: List[str],
        dependant_type: str = "hard"
    ):
        self.task_id = task_id
        self.depends_on = depends_on
        self.dependant_type = dependant_type

    def is_satisfied(self, completed_tasks: List[str]) -> bool:
        if self.dependant_type == "hard":
            return all(dep in completed_tasks for dep in self.depends_on)
        elif self.dependant_type == "soft":
            return any(dep in completed_tasks for dep in self.depends_on)
        return True

class AgentProtocol:
    @staticmethod
    def validate_request(request: TaskRequest) -> bool:
        required_fields = ["task_id", "task_type", "intent", "parameters"]
        return all(hasattr(request, field) for field in required_fields)

    @staticmethod
    def add_trust_chain(token_payload: Dict[str, Any], agent_id: str, action: str) -> Dict[str, Any]:
        new_chain = token_payload.get("chain_of_trust", []).copy()
        new_chain.append({
            "agent_id": agent_id,
            "agent_type": token_payload.get("agent_role", "agent"),
            "action": action,
            "timestamp": int(time.time()),
            "task_id": token_payload.get("task_id", "")
        })
        return new_chain
