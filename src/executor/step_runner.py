"""
Step Runner — executes a single step with retry logic and timeout enforcement.

This is the innermost execution unit. The executor calls this for each step.
"""

import time
from typing import Optional

from core.types import StepPlan, StepResult, StepStatus, ToolResult
from core.state import ExecutionState
from core.config import Config
from tools.registry import ToolRegistry


class StepRunner:
    """
    Executes a single step from the plan with:
    - Retry logic (exponential backoff)
    - Fallback action support
    - Timeout enforcement
    - Result standardization
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def run(
        self,
        step: StepPlan,
        state: ExecutionState,
        max_retries: Optional[int] = None,
    ) -> StepResult:
        """
        Execute a single step with retry logic.
        
        Args:
            step: The step plan to execute
            state: Shared execution state
            max_retries: Override step's max_retries
        
        Returns:
            StepResult with outcome details
        """
        retries = max_retries if max_retries is not None else step.max_retries
        start_time = time.time()
        last_error = None

        for attempt in range(retries + 1):
            if attempt > 0:
                # Exponential backoff: 1s, 2s, 4s...
                wait = min(2 ** (attempt - 1), 10)
                print(f"   🔄 Retry {attempt}/{retries} (waiting {wait}s)...")
                time.sleep(wait)

            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > step.timeout_seconds:
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.FAILED,
                    error=f"Timed out after {step.timeout_seconds}s",
                    retries_used=attempt,
                    duration_seconds=elapsed,
                )

            # Execute
            result = self.registry.execute_step(step, state)

            if result.is_success():
                duration = time.time() - start_time
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.SUCCESS,
                    tool_result=result,
                    retries_used=attempt,
                    duration_seconds=duration,
                )

            # Failed — check if retryable
            last_error = result.error or result.message
            if not result.retryable:
                break  # Don't retry non-retryable errors

        # All retries exhausted — try fallback if available
        if step.fallback_action:
            print(f"   ⤵️  Trying fallback: {step.tool}.{step.fallback_action}")
            fallback_step = StepPlan(
                id=step.id,
                tool=step.tool,
                action=step.fallback_action,
                args=step.fallback_args or step.args,
                description=f"Fallback for: {step.description}",
                max_retries=0,  # No retries on fallback
                timeout_seconds=step.timeout_seconds,
            )
            fallback_result = self.registry.execute_step(fallback_step, state)

            if fallback_result.is_success():
                duration = time.time() - start_time
                return StepResult(
                    step_id=step.id,
                    status=StepStatus.SUCCESS,
                    tool_result=fallback_result,
                    retries_used=retries + 1,
                    duration_seconds=duration,
                )

            last_error = fallback_result.error or fallback_result.message

        # Everything failed
        duration = time.time() - start_time
        return StepResult(
            step_id=step.id,
            status=StepStatus.FAILED,
            tool_result=ToolResult.fail(last_error or "Unknown error"),
            retries_used=retries,
            duration_seconds=duration,
            error=last_error,
        )
