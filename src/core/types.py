"""
Standard types used across the agent system.
All tool results, step plans, and status codes follow these contracts.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ─── Status Enums ───────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    REPLANNING = "replanning"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class DecisionType(str, Enum):
    TASK = "task"
    SIMPLE_REPLY = "simple_reply"


# ─── Tool Result (every tool MUST return this) ──────────────────

@dataclass
class ToolResult:
    """Standardized result from any tool execution."""
    status: str  # "success" | "fail" | "error" | "blocked"
    result: Any = None
    message: str = ""
    state_update: dict = field(default_factory=dict)
    error: Optional[str] = None
    retryable: bool = False

    def is_success(self) -> bool:
        return self.status == "success"

    def is_failure(self) -> bool:
        return self.status in ("fail", "error")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "result": self.result,
            "message": self.message,
            "state_update": self.state_update,
            "error": self.error,
            "retryable": self.retryable,
        }

    @classmethod
    def success(cls, result: Any = None, message: str = "", state_update: dict = None) -> "ToolResult":
        return cls(status="success", result=result, message=message, state_update=state_update or {})

    @classmethod
    def fail(cls, error: str, retryable: bool = True, result: Any = None) -> "ToolResult":
        return cls(status="fail", error=error, retryable=retryable, result=result)

    @classmethod
    def error(cls, error: str, retryable: bool = False) -> "ToolResult":
        return cls(status="error", error=error, retryable=retryable)


# ─── Step Plan (one atomic unit of work) ─────────────────────────

@dataclass
class StepPlan:
    """A single step in a task plan."""
    id: int
    tool: str
    action: str
    args: dict = field(default_factory=dict)
    description: str = ""
    depends_on: list[int] = field(default_factory=list)
    fallback_action: Optional[str] = None
    fallback_args: Optional[dict] = None
    max_retries: int = 2
    timeout_seconds: int = 30

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tool": self.tool,
            "action": self.action,
            "args": self.args,
            "description": self.description,
            "depends_on": self.depends_on,
            "fallback_action": self.fallback_action,
            "fallback_args": self.fallback_args,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepPlan":
        return cls(
            id=data["id"],
            tool=data["tool"],
            action=data["action"],
            args=data.get("args", {}),
            description=data.get("description", ""),
            depends_on=data.get("depends_on", []),
            fallback_action=data.get("fallback_action"),
            fallback_args=data.get("fallback_args"),
            max_retries=data.get("max_retries", 2),
            timeout_seconds=data.get("timeout_seconds", 30),
        )


# ─── Step Result (step + outcome) ───────────────────────────────

@dataclass
class StepResult:
    """Outcome of executing a single step."""
    step_id: int
    status: StepStatus
    tool_result: Optional[ToolResult] = None
    retries_used: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "result": self.tool_result.to_dict() if self.tool_result else None,
            "retries_used": self.retries_used,
            "duration_seconds": round(self.duration_seconds, 2),
            "error": self.error,
        }


# ─── Task Result (overall task outcome) ─────────────────────────

@dataclass
class TaskResult:
    """Final result of a complete task execution."""
    status: TaskStatus
    steps_completed: int = 0
    steps_total: int = 0
    replans: int = 0
    step_results: list[StepResult] = field(default_factory=list)
    final_state: Optional[dict] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "replans": self.replans,
            "step_results": [sr.to_dict() for sr in self.step_results],
            "final_state": self.final_state,
            "error": self.error,
        }


# ─── Agent Decision (routing result) ────────────────────────────

@dataclass
class AgentDecision:
    """Result of intent classification."""
    type: DecisionType
    confidence: float
    extracted_goal: str = ""
    reasoning: str = ""

    def is_task(self) -> bool:
        return self.type == DecisionType.TASK


# ─── Agent Response (final output) ──────────────────────────────

@dataclass
class AgentResponse:
    """Top-level response from MainAgent."""
    message: str = ""
    task_result: Optional[TaskResult] = None
    state_snapshot: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "task_result": self.task_result.to_dict() if self.task_result else None,
            "state": self.state_snapshot,
        }
