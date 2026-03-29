"""
Task Planner — LLM-powered task decomposition and replanning.

Converts a user goal + available tools into a structured plan of atomic steps.
Can also replan dynamically when steps fail.
"""

import json
import time
from openai import OpenAI
from typing import Optional

from core.types import StepPlan
from core.state import ExecutionState
from core.config import Config
from core.exceptions import PlannerError
from tools.registry import ToolRegistry
from planner.prompts import build_planner_prompt, REPLAN_PROMPT


class TaskPlanner:
    """
    LLM-powered planner that converts goals into executable step plans.
    
    Usage:
        planner = TaskPlanner(registry)
        steps = planner.plan("List all Python files in current directory")
        # Returns: [StepPlan(id=1, tool="cli", action="run_command", args={"command": "find . -name '*.py'"})]
    """

    def __init__(
        self,
        registry: ToolRegistry,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.registry = registry
        self.model = model or Config.PLANNER_MODEL
        self.api_key = api_key or Config.get_api_key()

        if not self.api_key:
            raise PlannerError("No API key configured — set NVIDIA_API_KEY in .env")

        # Use OpenAI SDK with NVIDIA endpoint
        provider = Config.get_provider()
        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "nvidia":
            base_url = "https://integrate.api.nvidia.com/v1"
        else:
            base_url = "https://openrouter.ai/api/v1"

        self.client = OpenAI(base_url=base_url, api_key=self.api_key)

    def plan(self, goal: str, state: Optional[ExecutionState] = None) -> list[StepPlan]:
        """
        Generate a structured plan for a goal.
        
        Args:
            goal: The user's goal in natural language
            state: Current execution state (optional, provides context)
        
        Returns:
            List of StepPlan objects ready for the executor
        """
        # Build tool catalog for the prompt
        tools_catalog = self.registry.format_for_llm()
        system_prompt = build_planner_prompt(tools_catalog)

        # Build user message
        user_message = f"Goal: {goal}"
        if state:
            state_context = state.format_for_llm()
            if state_context:
                user_message += f"\n\n{state_context}"

        # Call LLM
        raw_response = self._call_llm(system_prompt, user_message)

        # Parse into StepPlans
        steps = self._parse_plan(raw_response)

        if not steps:
            raise PlannerError("Planner generated an empty plan", raw_response)

        # Cap at max steps
        if len(steps) > Config.MAX_PLAN_STEPS:
            steps = steps[:Config.MAX_PLAN_STEPS]

        return steps

    def replan(
        self,
        goal: str,
        failed_step: StepPlan,
        error: str,
        state: ExecutionState,
        completed_steps: list[StepPlan],
    ) -> list[StepPlan]:
        """
        Generate a new plan after a failure.
        
        Takes into account what already completed and what went wrong.
        """
        # Format completed steps description
        completed_desc = "\n".join(
            f"- Step {s.id}: {s.description} (tool={s.tool}, action={s.action}) ✅"
            for s in completed_steps
        )

        system_prompt = REPLAN_PROMPT.format(
            goal=goal,
            failed_step_id=failed_step.id,
            failed_description=f"{failed_step.tool}.{failed_step.action}: {failed_step.description}",
            error=error,
            state_context=state.format_for_llm(),
            completed_steps=completed_desc or "None",
        )

        # Include tool catalog
        tools_catalog = self.registry.format_for_llm()
        system_prompt += f"\n\n{tools_catalog}"

        user_message = f"Replan the task: {goal}"

        raw_response = self._call_llm(system_prompt, user_message)
        steps = self._parse_plan(raw_response)

        # Check for IMPOSSIBLE signal
        if steps and "IMPOSSIBLE" in steps[0].description:
            raise PlannerError(f"Task deemed impossible: {steps[0].description}")

        return steps

    # ─── LLM Communication ──────────────────────────────────────

    def _call_llm(self, system_prompt: str, user_message: str, max_retries: int = 3) -> str:
        """Call the LLM API via OpenAI SDK with streaming and retry logic."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        for attempt in range(max_retries):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                    top_p=1,
                    max_tokens=4096,
                    stream=True,
                )

                # Collect streamed response
                full_response = ""
                for chunk in completion:
                    if not getattr(chunk, "choices", None):
                        continue
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content

                if full_response:
                    return full_response

                raise PlannerError("Empty response from LLM")

            except PlannerError:
                raise

            except Exception as e:
                error_msg = str(e)

                # Rate limit — back off and retry
                if "429" in error_msg and attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    print(f"⏳ Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                # Timeout / connection errors — retry
                if ("timeout" in error_msg.lower() or "connection" in error_msg.lower()) and attempt < max_retries - 1:
                    print(f"⏳ Connection issue, retrying...")
                    time.sleep(3)
                    continue

                # Final attempt or unrecoverable error
                if attempt >= max_retries - 1:
                    raise PlannerError(f"LLM API error after {max_retries} attempts: {error_msg}")

                raise PlannerError(f"LLM error: {error_msg}")

    # ─── Plan Parsing ───────────────────────────────────────────

    def _parse_plan(self, raw: str) -> list[StepPlan]:
        """Parse raw LLM output into StepPlan objects."""
        # Extract JSON array from response
        json_str = self._extract_json(raw)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise PlannerError(f"Invalid JSON from planner: {str(e)}", raw)

        if not isinstance(data, list):
            raise PlannerError("Planner output must be a JSON array", raw)

        steps = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue

            # Ensure required fields
            if "tool" not in item or "action" not in item:
                continue

            # Auto-assign ID if missing
            if "id" not in item:
                item["id"] = i + 1

            try:
                step = StepPlan.from_dict(item)
                steps.append(step)
            except (KeyError, TypeError) as e:
                print(f"⚠️ Skipping malformed step {i}: {e}")
                continue

        return steps

    def _extract_json(self, text: str) -> str:
        """Extract JSON array from LLM response (handles markdown code blocks)."""
        # Try to find JSON array directly
        text = text.strip()

        # Remove markdown code fences
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                text = text[start:end].strip()

        # Find the JSON array
        bracket_start = text.find("[")
        bracket_end = text.rfind("]") + 1

        if bracket_start >= 0 and bracket_end > bracket_start:
            return text[bracket_start:bracket_end]

        return text
