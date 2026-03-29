"""
Custom exception hierarchy for the agent system.
Clear, typed errors that the executor can catch and handle appropriately.
"""


class AgentError(Exception):
    """Base exception for all agent errors."""
    pass


class ToolError(AgentError):
    """Raised when a tool fails to execute."""
    def __init__(self, tool_name: str, action: str, message: str, retryable: bool = True):
        self.tool_name = tool_name
        self.action = action
        self.retryable = retryable
        super().__init__(f"[{tool_name}.{action}] {message}")


class ToolNotFoundError(AgentError):
    """Raised when a requested tool doesn't exist in the registry."""
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool not found: '{tool_name}'")


class InvalidActionError(AgentError):
    """Raised when a tool doesn't support the requested action."""
    def __init__(self, tool_name: str, action: str, valid_actions: list[str]):
        self.tool_name = tool_name
        self.action = action
        self.valid_actions = valid_actions
        super().__init__(
            f"Tool '{tool_name}' does not support action '{action}'. "
            f"Valid actions: {valid_actions}"
        )


class PlannerError(AgentError):
    """Raised when the planner fails to generate a valid plan."""
    def __init__(self, message: str, raw_response: str = ""):
        self.raw_response = raw_response
        super().__init__(f"Planner error: {message}")


class ExecutorError(AgentError):
    """Raised when the executor encounters an unrecoverable error."""
    pass


class MaxRetriesExceeded(AgentError):
    """Raised when a step exhausts all retry attempts."""
    def __init__(self, step_id: int, retries: int, last_error: str):
        self.step_id = step_id
        self.retries = retries
        self.last_error = last_error
        super().__init__(f"Step {step_id} failed after {retries} retries: {last_error}")


class MaxReplansExceeded(AgentError):
    """Raised when re-planning exceeds the maximum allowed attempts."""
    def __init__(self, replans: int, last_error: str):
        self.replans = replans
        self.last_error = last_error
        super().__init__(f"Max replans ({replans}) exceeded: {last_error}")


class StateError(AgentError):
    """Raised when state is corrupted or inaccessible."""
    pass


class TimeoutError(AgentError):
    """Raised when a step exceeds its timeout."""
    def __init__(self, step_id: int, timeout_seconds: int):
        self.step_id = step_id
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Step {step_id} timed out after {timeout_seconds}s")
