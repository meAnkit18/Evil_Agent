"""
Task Executor — THE CORE ENGINE.

This is the heart of the agent system.
Runs the execution loop: validate → execute → check result → update state → decide next.

NOT a simple for-loop. This is a stateful engine with:
- Shared state propagation
- Automatic retry with fallback
- Dynamic replanning on failure
- Progress reporting
- Max depth guard against infinite loops
"""

import time
from typing import Optional, Callable

from core.types import (
    StepPlan, StepResult, TaskResult,
    TaskStatus, StepStatus, ToolResult,
)
from core.state import ExecutionState
from core.config import Config
from core.exceptions import MaxReplansExceeded
from tools.registry import ToolRegistry
from planner.planner import TaskPlanner
from planner.validator import PlanValidator
from executor.step_runner import StepRunner
from executor.replanner import Replanner


class TaskExecutor:
    """
    The execution loop engine.
    
    Usage:
        executor = TaskExecutor(registry, planner)
        result = executor.run(plan, state, goal="List Python files")
    """

    def __init__(
        self,
        registry: ToolRegistry,
        planner: TaskPlanner,
        on_step_complete: Optional[Callable] = None,
        on_replan: Optional[Callable] = None,
    ):
        self.registry = registry
        self.planner = planner
        self.validator = PlanValidator(registry)
        self.step_runner = StepRunner(registry)
        self.replanner = Replanner(planner, registry)

        # Progress callbacks (for UI/websocket updates)
        self.on_step_complete = on_step_complete
        self.on_replan = on_replan

    def run(
        self,
        plan: list[StepPlan],
        state: ExecutionState,
        goal: str = "",
    ) -> TaskResult:
        """
        Execute a plan step by step.
        
        The main loop:
            for each step:
                1. Check dependencies
                2. Validate step
                3. Execute with retry
                4. Handle failure (replan if needed)
                5. Update shared state
                6. Record result
        
        Args:
            plan: List of StepPlan to execute
            state: Shared execution state
            goal: The original goal (needed for replanning)
        
        Returns:
            TaskResult with overall outcome
        """
        print(f"\n⚡ Executing plan ({len(plan)} steps)")
        print("─" * 50)

        start_time = time.time()
        step_results: list[StepResult] = []
        completed_steps: list[StepPlan] = []
        total_steps = len(plan)

        # Reset replanner
        self.replanner.reset()

        current_plan = list(plan)
        step_index = 0

        while step_index < len(current_plan):
            step = current_plan[step_index]
            step_num = step_index + 1

            print(f"\n{'='*50}")
            print(f"📌 Step {step_num}/{len(current_plan)}: [{step.tool}] {step.action}")
            if step.description:
                print(f"   📝 {step.description}")

            # ─── 1. CHECK DEPENDENCIES ─────────────────────────
            deps_ok, dep_error = self._check_dependencies(step, state)
            if not deps_ok:
                print(f"   ⏭️  Skipping: {dep_error}")
                state.mark_skipped(step.id, dep_error)
                step_results.append(StepResult(
                    step_id=step.id,
                    status=StepStatus.SKIPPED,
                    error=dep_error,
                ))
                step_index += 1
                continue

            # ─── 2. VALIDATE ───────────────────────────────────
            is_valid, val_error = self.registry.validate_step(step)
            if not is_valid:
                print(f"   ❌ Validation failed: {val_error}")
                # Try replanning instead of just failing
                new_plan = self._try_replan(
                    goal, step, val_error, state, completed_steps,
                    current_plan[step_index + 1:],
                )
                if new_plan:
                    current_plan = current_plan[:step_index] + new_plan
                    continue
                else:
                    state.mark_failed(step.id, val_error)
                    step_results.append(StepResult(
                        step_id=step.id,
                        status=StepStatus.FAILED,
                        error=val_error,
                    ))
                    return self._build_result(
                        TaskStatus.FAILED, step_results,
                        completed_steps, state, start_time,
                        error=val_error,
                    )

            # ─── 3. RESOLVE ARGS ──────────────────────────────
            # Replace {state.step_X_result} / {state.last_output} placeholders
            resolved_step = self._resolve_args(step, state)

            # ─── 4. EXECUTE ───────────────────────────────────
            print(f"   ⚡ Executing...")
            step_result = self.step_runner.run(resolved_step, state)

            # ─── 4. HANDLE RESULT ─────────────────────────────
            if step_result.status == StepStatus.SUCCESS:
                # Success!
                print(f"   ✅ Success", end="")
                if step_result.tool_result and step_result.tool_result.message:
                    print(f": {step_result.tool_result.message[:100]}")
                else:
                    print()

                # Update shared state
                if step_result.tool_result and step_result.tool_result.state_update:
                    state.update(step_result.tool_result.state_update)

                state.mark_completed(
                    step.id,
                    step_result.tool_result.result if step_result.tool_result else None,
                )
                completed_steps.append(step)
                step_results.append(step_result)

                # Progress callback
                if self.on_step_complete:
                    self.on_step_complete(step, step_result, state)

                step_index += 1

            elif step_result.status == StepStatus.FAILED:
                error_msg = step_result.error or "Unknown failure"
                print(f"   ❌ Failed: {error_msg[:100]}")

                # Auto-inspect on browser failure — give the replanner real selectors
                if step.tool == "browser" and self.registry.has("browser"):
                    self._auto_inspect(state)

                # Try replanning
                new_plan = self._try_replan(
                    goal, step, error_msg, state, completed_steps,
                    current_plan[step_index + 1:],
                )

                if new_plan:
                    # Replace remaining plan with new plan
                    current_plan = current_plan[:step_index] + new_plan
                    total_steps = len(completed_steps) + len(current_plan) - step_index
                    # Don't increment step_index — re-execute from current position
                    continue
                else:
                    # Replanning failed — abort
                    state.mark_failed(step.id, error_msg)
                    step_results.append(step_result)
                    return self._build_result(
                        TaskStatus.FAILED, step_results,
                        completed_steps, state, start_time,
                        error=error_msg,
                    )

            else:
                # Blocked or other status
                print(f"   ⚠️ Status: {step_result.status.value}")
                step_results.append(step_result)
                step_index += 1

        # All steps completed!
        print(f"\n{'='*50}")
        print("✅ All steps completed successfully!")
        duration = time.time() - start_time
        print(f"⏱️  Total time: {duration:.1f}s")

        return self._build_result(
            TaskStatus.SUCCESS, step_results,
            completed_steps, state, start_time,
        )

    # ─── Replanning ─────────────────────────────────────────────

    def _try_replan(
        self,
        goal: str,
        failed_step: StepPlan,
        error: str,
        state: ExecutionState,
        completed_steps: list[StepPlan],
        remaining_steps: list[StepPlan],
    ) -> Optional[list[StepPlan]]:
        """Attempt to replan. Returns new steps or None."""
        if not goal:
            return None  # Can't replan without a goal

        try:
            new_plan = self.replanner.replan(
                goal=goal,
                failed_step=failed_step,
                error=error,
                state=state,
                completed_steps=completed_steps,
                remaining_steps=remaining_steps,
            )

            if new_plan and self.on_replan:
                self.on_replan(failed_step, new_plan, state)

            return new_plan

        except MaxReplansExceeded as e:
            print(f"   🛑 {e}")
            return None

    # ─── Auto-Inspect on Browser Failure ────────────────────────

    def _auto_inspect(self, state: ExecutionState):
        """
        When a browser step fails, automatically inspect the page to discover
        real CSS selectors. Results are stored in state so the replanner can use them.
        """
        try:
            browser_tool = self.registry.get("browser")
            if browser_tool:
                print("   🔍 Auto-inspecting page for real selectors...")
                inspect_result = browser_tool.execute("inspect", {}, state)
                if inspect_result.is_success():
                    # Store elements in state for replanner to see
                    elements_text = str(inspect_result.result or inspect_result.message)
                    state.set("custom.page_elements", elements_text[:3000])
                    print(f"   📋 Found page elements (stored in state for replanning)")
        except Exception as e:
            print(f"   ⚠️ Auto-inspect failed: {e}")

    # ─── Arg Resolution ───────────────────────────────────────────

    def _resolve_args(self, step: StepPlan, state: ExecutionState) -> StepPlan:
        """
        Resolve {state.step_X_result} and {state.last_output} placeholders in step args.
        
        This enables data flow between steps:
        - Step 2 extracts text → stored in state
        - Step 3 uses {state.step_2_result} in its args → resolved to actual text
        """
        import re
        import copy

        resolved_args = copy.deepcopy(step.args)

        for key, value in resolved_args.items():
            if not isinstance(value, str):
                continue

            # Replace {state.step_X_result} with actual step output
            pattern = r'\{state\.step_(\d+)_result\}'
            matches = re.findall(pattern, value)
            for step_id_str in matches:
                step_id = int(step_id_str)
                result = state.get_step_result(step_id)
                if result is not None:
                    placeholder = f"{{state.step_{step_id_str}_result}}"
                    resolved_args[key] = resolved_args[key].replace(placeholder, str(result))

            # Replace {state.last_output} with last tool output
            if "{state.last_output}" in resolved_args[key]:
                last_output = state.get("last_output")
                if last_output is not None:
                    resolved_args[key] = resolved_args[key].replace(
                        "{state.last_output}", str(last_output)
                    )

        # Return a new StepPlan with resolved args
        return StepPlan(
            id=step.id,
            tool=step.tool,
            action=step.action,
            args=resolved_args,
            description=step.description,
            depends_on=step.depends_on,
            fallback_action=step.fallback_action,
            fallback_args=step.fallback_args,
        )

    # ─── Dependencies ───────────────────────────────────────────

    def _check_dependencies(
        self, step: StepPlan, state: ExecutionState
    ) -> tuple[bool, str]:
        """Check if all dependencies for a step are met."""
        for dep_id in step.depends_on:
            if not state.is_step_completed(dep_id):
                return False, f"Dependency step {dep_id} not completed"
        return True, ""

    # ─── Result Builder ─────────────────────────────────────────

    def _build_result(
        self,
        status: TaskStatus,
        step_results: list[StepResult],
        completed_steps: list[StepPlan],
        state: ExecutionState,
        start_time: float,
        error: str = None,
    ) -> TaskResult:
        total = len(step_results)
        completed = sum(1 for r in step_results if r.status == StepStatus.SUCCESS)

        return TaskResult(
            status=status,
            steps_completed=completed,
            steps_total=total,
            replans=self.replanner.replan_count,
            step_results=step_results,
            final_state=state.snapshot(),
            error=error,
        )
