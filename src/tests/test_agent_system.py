"""
Unit tests for the core infrastructure, tool registry, and executor.
"""

import os
import sys
import json
import pytest

# Ensure src is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════
# TEST: ExecutionState
# ═══════════════════════════════════════════════════════════════

class TestExecutionState:
    def test_creation(self):
        from core.state import ExecutionState
        state = ExecutionState()
        assert state.get("current_url") is None
        assert state.get("logged_in") is False
        assert state.completed_count() == 0

    def test_update_and_get(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.update({"current_url": "https://example.com", "logged_in": True})
        assert state.get("current_url") == "https://example.com"
        assert state.get("logged_in") is True

    def test_dotted_keys(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.update({"custom.my_key": "hello"})
        assert state.get("custom.my_key") == "hello"

    def test_snapshot_is_copy(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.set("current_url", "https://test.com")
        snap = state.snapshot()
        snap["current_url"] = "MUTATED"
        assert state.get("current_url") == "https://test.com"

    def test_step_tracking(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.mark_completed(1, "output1")
        state.mark_completed(2, "output2")
        assert state.completed_count() == 2
        assert state.is_step_completed(1)
        assert not state.is_step_completed(3)

    def test_failure_tracking(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.mark_failed(1, "some error")
        assert state.failure_count() == 1
        assert state.consecutive_failures == 1
        state.mark_completed(2)
        assert state.consecutive_failures == 0

    def test_format_for_llm(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.set("current_url", "https://test.com")
        state.mark_completed(1, "done")
        text = state.format_for_llm()
        assert "https://test.com" in text
        assert "Step 1" in text

    def test_reset(self):
        from core.state import ExecutionState
        state = ExecutionState()
        state.mark_completed(1)
        state.mark_failed(2, "err")
        state.reset()
        assert state.completed_count() == 0
        assert state.failure_count() == 0


# ═══════════════════════════════════════════════════════════════
# TEST: ToolResult
# ═══════════════════════════════════════════════════════════════

class TestToolResult:
    def test_success(self):
        from core.types import ToolResult
        r = ToolResult.success(result="hello", message="done")
        assert r.is_success()
        assert not r.is_failure()
        assert r.result == "hello"

    def test_fail(self):
        from core.types import ToolResult
        r = ToolResult.fail("something broke", retryable=True)
        assert r.is_failure()
        assert r.retryable is True

    def test_to_dict(self):
        from core.types import ToolResult
        r = ToolResult.success(result=42, state_update={"x": 1})
        d = r.to_dict()
        assert d["status"] == "success"
        assert d["result"] == 42
        assert d["state_update"] == {"x": 1}


# ═══════════════════════════════════════════════════════════════
# TEST: StepPlan
# ═══════════════════════════════════════════════════════════════

class TestStepPlan:
    def test_from_dict(self):
        from core.types import StepPlan
        data = {
            "id": 1,
            "tool": "cli",
            "action": "run_command",
            "args": {"command": "ls"},
            "description": "List files",
        }
        step = StepPlan.from_dict(data)
        assert step.id == 1
        assert step.tool == "cli"
        assert step.action == "run_command"

    def test_to_dict(self):
        from core.types import StepPlan
        step = StepPlan(id=1, tool="cli", action="run_command", args={"command": "ls"})
        d = step.to_dict()
        assert d["tool"] == "cli"
        assert d["args"]["command"] == "ls"


# ═══════════════════════════════════════════════════════════════
# TEST: Tool Registry
# ═══════════════════════════════════════════════════════════════

class TestToolRegistry:
    def test_register_and_get(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        reg = ToolRegistry()
        reg.register(CLITool())
        assert reg.has("cli")
        tool = reg.get("cli")
        assert tool.name == "cli"

    def test_list_tools(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from tools.file_tool import FileTool
        reg = ToolRegistry()
        reg.register(CLITool())
        reg.register(FileTool())
        tools = reg.list_tools()
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "cli" in names
        assert "file" in names

    def test_validate_step_valid(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from core.types import StepPlan
        reg = ToolRegistry()
        reg.register(CLITool())
        step = StepPlan(id=1, tool="cli", action="run_command", args={"command": "ls"})
        valid, error = reg.validate_step(step)
        assert valid is True

    def test_validate_step_bad_tool(self):
        from tools.registry import ToolRegistry
        from core.types import StepPlan
        reg = ToolRegistry()
        step = StepPlan(id=1, tool="nonexistent", action="run", args={})
        valid, error = reg.validate_step(step)
        assert valid is False
        assert "not found" in error

    def test_validate_step_bad_action(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from core.types import StepPlan
        reg = ToolRegistry()
        reg.register(CLITool())
        step = StepPlan(id=1, tool="cli", action="fly_to_moon", args={})
        valid, error = reg.validate_step(step)
        assert valid is False

    def test_validate_step_bad_args(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from core.types import StepPlan
        reg = ToolRegistry()
        reg.register(CLITool())
        step = StepPlan(id=1, tool="cli", action="run_command", args={})  # missing 'command'
        valid, error = reg.validate_step(step)
        assert valid is False

    def test_tool_not_found_error(self):
        from tools.registry import ToolRegistry
        from core.exceptions import ToolNotFoundError
        reg = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            reg.get("doesnt_exist")

    def test_format_for_llm(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        reg = ToolRegistry()
        reg.register(CLITool())
        text = reg.format_for_llm()
        assert "cli" in text
        assert "run_command" in text


# ═══════════════════════════════════════════════════════════════
# TEST: CLI Tool
# ═══════════════════════════════════════════════════════════════

class TestCLITool:
    def test_run_command(self):
        from tools.cli_tool import CLITool
        from core.state import ExecutionState
        tool = CLITool()
        state = ExecutionState()
        result = tool.execute("run_command", {"command": "echo hello"}, state)
        assert result.is_success()
        assert "hello" in result.result

    def test_blocked_command(self):
        from tools.cli_tool import CLITool
        from core.state import ExecutionState
        tool = CLITool()
        state = ExecutionState()
        result = tool.execute("run_command", {"command": "rm -rf /"}, state)
        assert result.is_failure()
        assert result.retryable is False

    def test_list_dir(self):
        from tools.cli_tool import CLITool
        from core.state import ExecutionState
        tool = CLITool()
        state = ExecutionState()
        result = tool.execute("list_dir", {"path": "/tmp"}, state)
        assert result.is_success()
        assert isinstance(result.result, list)


# ═══════════════════════════════════════════════════════════════
# TEST: File Tool
# ═══════════════════════════════════════════════════════════════

class TestFileTool:
    def test_write_and_read(self):
        from tools.file_tool import FileTool
        from core.state import ExecutionState
        tool = FileTool()
        state = ExecutionState()

        path = "/tmp/evil_agent_test_file.txt"
        tool.execute("write", {"path": path, "content": "test data"}, state)
        result = tool.execute("read", {"path": path}, state)
        assert result.is_success()
        assert "test data" in result.result

        # Cleanup
        tool.execute("delete", {"path": path}, state)

    def test_exists(self):
        from tools.file_tool import FileTool
        from core.state import ExecutionState
        tool = FileTool()
        state = ExecutionState()
        result = tool.execute("exists", {"path": "/tmp"}, state)
        assert result.is_success()
        assert result.result["exists"] is True
        assert result.result["type"] == "directory"


# ═══════════════════════════════════════════════════════════════
# TEST: System Tool
# ═══════════════════════════════════════════════════════════════

class TestSystemTool:
    def test_os_info(self):
        from tools.system_tool import SystemTool
        from core.state import ExecutionState
        tool = SystemTool()
        state = ExecutionState()
        result = tool.execute("get_os_info", {}, state)
        assert result.is_success()
        assert "os" in result.result

    def test_get_time(self):
        from tools.system_tool import SystemTool
        from core.state import ExecutionState
        tool = SystemTool()
        state = ExecutionState()
        result = tool.execute("get_time", {}, state)
        assert result.is_success()

    def test_check_command(self):
        from tools.system_tool import SystemTool
        from core.state import ExecutionState
        tool = SystemTool()
        state = ExecutionState()
        result = tool.execute("check_command", {"command": "python3"}, state)
        assert result.is_success()
        assert result.result["available"] is True


# ═══════════════════════════════════════════════════════════════
# TEST: Plan Validator
# ═══════════════════════════════════════════════════════════════

class TestPlanValidator:
    def test_valid_plan(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from planner.validator import PlanValidator
        from core.types import StepPlan
        reg = ToolRegistry()
        reg.register(CLITool())
        validator = PlanValidator(reg)
        plan = [
            StepPlan(id=1, tool="cli", action="run_command", args={"command": "ls"}),
            StepPlan(id=2, tool="cli", action="run_command", args={"command": "pwd"}, depends_on=[1]),
        ]
        result = validator.validate(plan)
        assert result["valid"] is True

    def test_invalid_tool(self):
        from tools.registry import ToolRegistry
        from planner.validator import PlanValidator
        from core.types import StepPlan
        reg = ToolRegistry()
        validator = PlanValidator(reg)
        plan = [StepPlan(id=1, tool="magic", action="cast_spell", args={})]
        result = validator.validate(plan)
        assert result["valid"] is False

    def test_circular_dependency(self):
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from planner.validator import PlanValidator
        from core.types import StepPlan
        reg = ToolRegistry()
        reg.register(CLITool())
        validator = PlanValidator(reg)
        plan = [
            StepPlan(id=1, tool="cli", action="run_command", args={"command": "ls"}, depends_on=[1]),
        ]
        result = validator.validate(plan)
        assert result["valid"] is False


# ═══════════════════════════════════════════════════════════════
# TEST: Executor with Mock
# ═══════════════════════════════════════════════════════════════

class TestExecutorWithMock:
    def test_simple_plan_execution(self):
        """Test executor with real CLI tool on a simple plan."""
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from tools.system_tool import SystemTool
        from core.types import StepPlan, TaskStatus
        from core.state import ExecutionState
        from executor.step_runner import StepRunner

        reg = ToolRegistry()
        reg.register(CLITool())
        reg.register(SystemTool())

        runner = StepRunner(reg)
        state = ExecutionState()

        step = StepPlan(
            id=1, tool="cli", action="run_command",
            args={"command": "echo 'test passed'"},
            description="Test echo",
        )
        result = runner.run(step, state)
        assert result.status.value == "success"
        assert "test passed" in result.tool_result.result

    def test_state_propagation(self):
        """Test that state updates propagate between steps."""
        from tools.registry import ToolRegistry
        from tools.cli_tool import CLITool
        from core.types import StepPlan
        from core.state import ExecutionState
        from executor.step_runner import StepRunner

        reg = ToolRegistry()
        reg.register(CLITool())
        runner = StepRunner(reg)
        state = ExecutionState()

        # Step 1: run pwd
        step1 = StepPlan(
            id=1, tool="cli", action="run_command",
            args={"command": "pwd"},
        )
        result1 = runner.run(step1, state)
        assert result1.status.value == "success"

        # State should have been updated with current_directory
        assert state.get("last_tool_used") == "cli"


# ═══════════════════════════════════════════════════════════════
# TEST: Router
# ═══════════════════════════════════════════════════════════════

class TestRouter:
    def test_task_keyword(self):
        from agents.main_agent.router import Router
        from core.types import DecisionType
        router = Router()
        decision = router._rule_based("create a file called test.py")
        assert decision is not None
        assert decision.type == DecisionType.TASK

    def test_question_pattern(self):
        from agents.main_agent.router import Router
        from core.types import DecisionType
        router = Router()
        decision = router._rule_based("what is Python?")
        assert decision is not None
        assert decision.type == DecisionType.SIMPLE_REPLY

    def test_polite_request(self):
        from agents.main_agent.router import Router
        from core.types import DecisionType
        router = Router()
        decision = router._rule_based("can you list the files?")
        assert decision is not None
        assert decision.type == DecisionType.TASK


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
