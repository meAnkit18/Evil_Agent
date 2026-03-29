"""
Base Tool — abstract class that every tool in the registry must implement.

Contract:
- Every tool has a name, description, and list of supported actions
- Every tool's execute() returns a ToolResult (no exceptions)
- Every tool validates its inputs before execution
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from core.types import ToolResult
from core.state import ExecutionState


class BaseTool(ABC):
    """
    Abstract base class for all tools in the agent system.
    
    Subclasses MUST:
    - Set name, description, and actions
    - Implement execute() returning ToolResult
    - Implement validate() returning (bool, error_msg)
    """

    name: str = ""
    description: str = ""
    actions: list[str] = []

    @abstractmethod
    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        """
        Execute an action with the given arguments.
        
        MUST return a ToolResult — never raise exceptions.
        If something fails, return ToolResult.fail() or ToolResult.error().
        
        Args:
            action: The action to perform (must be in self.actions)
            args: Action-specific arguments
            state: Current shared execution state (read + write)
        
        Returns:
            ToolResult with status, result, and state_update
        """
        pass

    def validate(self, action: str, args: dict) -> tuple[bool, str]:
        """
        Validate that an action + args combination is valid.
        
        Returns:
            (is_valid, error_message) — error_message is empty if valid
        """
        if action not in self.actions:
            return False, f"Unknown action '{action}'. Valid: {self.actions}"
        return True, ""

    def get_schema(self) -> dict:
        """
        Return tool metadata for LLM context.
        The planner uses this to know what tools are available.
        """
        return {
            "name": self.name,
            "description": self.description,
            "actions": self.actions,
        }

    def __repr__(self) -> str:
        return f"<Tool:{self.name} actions={self.actions}>"
