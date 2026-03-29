"""
Tool Registry — central hub for discovering, validating, and dispatching to tools.

The planner queries this to know what tools exist.
The executor queries this to validate steps before execution.
"""

from __future__ import annotations
from typing import Optional

from tools.base import BaseTool
from core.types import ToolResult, StepPlan
from core.state import ExecutionState
from core.exceptions import ToolNotFoundError, InvalidActionError


class ToolRegistry:
    """
    Singleton registry for all available tools.
    
    Usage:
        registry = ToolRegistry()
        registry.register(CLITool())
        registry.register(BrowserTool())
        
        # Planner uses this to generate tool catalog for LLM
        tools_for_llm = registry.list_tools()
        
        # Executor uses this to run a step
        result = registry.execute_step(step, state)
    """

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    # ─── Registration ───────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Overwrites if name already exists."""
        if not tool.name:
            raise ValueError(f"Tool {tool.__class__.__name__} must have a name")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """Remove a tool. Returns True if it existed."""
        return self._tools.pop(name, None) is not None

    # ─── Lookup ─────────────────────────────────────────────────

    def get(self, name: str) -> BaseTool:
        """Get a tool by name. Raises ToolNotFoundError if not found."""
        tool = self._tools.get(name)
        if not tool:
            raise ToolNotFoundError(name)
        return tool

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_names(self) -> list[str]:
        """Return all registered tool names."""
        return list(self._tools.keys())

    # ─── For LLM Context ────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """
        Return tool schemas for LLM prompt injection.
        The planner uses this to know what's available.
        """
        return [tool.get_schema() for tool in self._tools.values()]

    def format_for_llm(self) -> str:
        """Format all tools as a readable string for LLM prompts."""
        lines = ["## Available Tools\n"]
        for tool in self._tools.values():
            lines.append(f"### {tool.name}")
            lines.append(f"{tool.description}")
            lines.append(f"Actions: {', '.join(tool.actions)}")
            lines.append("")
        return "\n".join(lines)

    # ─── Validation ─────────────────────────────────────────────

    def validate_step(self, step: StepPlan) -> tuple[bool, str]:
        """
        Validate a step plan against the registry.
        
        Checks:
        1. Tool exists
        2. Action is valid for that tool
        3. Tool-specific arg validation
        
        Returns:
            (is_valid, error_message)
        """
        # Tool exists?
        if not self.has(step.tool):
            available = ", ".join(self.list_names())
            return False, f"Tool '{step.tool}' not found. Available: [{available}]"

        tool = self.get(step.tool)

        # Action valid?
        if step.action not in tool.actions:
            return False, f"Tool '{step.tool}' doesn't support action '{step.action}'. Valid: {tool.actions}"

        # Tool-specific validation
        is_valid, error = tool.validate(step.action, step.args)
        if not is_valid:
            return False, f"Validation failed for {step.tool}.{step.action}: {error}"

        return True, ""

    def validate_plan(self, steps: list[StepPlan]) -> list[dict]:
        """
        Validate an entire plan. Returns list of issues (empty = valid).
        """
        issues = []
        step_ids = {s.id for s in steps}

        for step in steps:
            # Validate the step itself
            is_valid, error = self.validate_step(step)
            if not is_valid:
                issues.append({"step_id": step.id, "error": error})

            # Validate dependencies exist
            for dep_id in step.depends_on:
                if dep_id not in step_ids:
                    issues.append({
                        "step_id": step.id,
                        "error": f"Depends on step {dep_id} which doesn't exist"
                    })

        return issues

    # ─── Execution ──────────────────────────────────────────────

    def execute_step(self, step: StepPlan, state: ExecutionState) -> ToolResult:
        """
        Execute a single step plan against the appropriate tool.
        
        This is the primary dispatch method used by the executor.
        """
        # Validate first
        is_valid, error = self.validate_step(step)
        if not is_valid:
            return ToolResult.error(error)

        tool = self.get(step.tool)

        # Update state with what we're doing
        state.set("last_tool_used", step.tool)
        state.set("last_action", step.action)

        # Execute
        try:
            result = tool.execute(step.action, step.args, state)
        except Exception as e:
            result = ToolResult.error(f"Unexpected error in {step.tool}.{step.action}: {str(e)}")

        return result

    # ─── Info ────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._tools)

    def __repr__(self) -> str:
        names = ", ".join(self.list_names())
        return f"<ToolRegistry tools=[{names}]>"
