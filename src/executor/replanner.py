"""
Replanner — dynamic replanning engine for when steps fail.

The executor calls this when a step fails and all retries are exhausted.
Takes the failure context + current state and generates a new plan.
"""

from typing import Optional

from core.types import StepPlan
from core.state import ExecutionState
from core.config import Config
from core.exceptions import MaxReplansExceeded, PlannerError
from planner.planner import TaskPlanner
from tools.registry import ToolRegistry


class Replanner:
    """
    Generates replacement plans when execution fails.
    
    Strategy:
    1. Take the failed step, the error, and the current state
    2. Ask the planner to generate alternative steps
    3. Merge new steps with remaining original steps
    4. Enforce a max replan limit to prevent infinite loops
    """

    def __init__(
        self,
        planner: TaskPlanner,
        registry: ToolRegistry,
        max_replans: Optional[int] = None,
    ):
        self.planner = planner
        self.registry = registry
        self.max_replans = max_replans or Config.MAX_REPLANS
        self._replan_count = 0

    def replan(
        self,
        goal: str,
        failed_step: StepPlan,
        error: str,
        state: ExecutionState,
        completed_steps: list[StepPlan],
        remaining_steps: list[StepPlan],
    ) -> Optional[list[StepPlan]]:
        """
        Generate a new plan from the failure point.
        
        Args:
            goal: Original user goal
            failed_step: The step that failed
            error: Error message from the failure
            state: Current execution state
            completed_steps: Steps already completed successfully
            remaining_steps: Steps not yet executed
        
        Returns:
            New list of StepPlan to execute, or None if replanning is impossible
        """
        self._replan_count += 1

        if self._replan_count > self.max_replans:
            raise MaxReplansExceeded(
                self._replan_count,
                f"Failed at step {failed_step.id}: {error}",
            )

        print(f"\n🔁 Replanning ({self._replan_count}/{self.max_replans})...")
        print(f"   Failed step: {failed_step.tool}.{failed_step.action}")
        print(f"   Error: {error[:100]}")

        try:
            new_steps = self.planner.replan(
                goal=goal,
                failed_step=failed_step,
                error=error,
                state=state,
                completed_steps=completed_steps,
            )

            if not new_steps:
                print("   ❌ Replanner returned empty plan")
                return None

            # Renumber steps to continue from where we left off
            max_completed_id = max(
                (s.id for s in completed_steps), default=0
            )
            for i, step in enumerate(new_steps):
                step.id = max_completed_id + i + 1

            # Validate new plan
            issues = self.registry.validate_plan(new_steps)
            if issues:
                print(f"   ⚠️ New plan has {len(issues)} validation issues")
                for issue in issues[:3]:
                    print(f"      - Step {issue['step_id']}: {issue['error']}")
                # Proceed anyway — executor will handle individual step failures

            print(f"   ✅ New plan: {len(new_steps)} steps")
            for step in new_steps:
                print(f"      {step.id}. [{step.tool}] {step.action}: {step.description}")

            return new_steps

        except PlannerError as e:
            print(f"   ❌ Replan failed: {e}")
            return None

    @property
    def replan_count(self) -> int:
        return self._replan_count

    def reset(self):
        """Reset replan counter for a new task."""
        self._replan_count = 0
