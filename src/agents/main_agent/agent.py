"""
Main Agent (CEO) — the top-level orchestrator.

This is the single entry point for all user interactions.
It decides what to do, delegates to the right components, and returns results.

Flow:
    user input → Router → (Task? → Planner → Executor)
                         → (Simple Question? → LLM Reply)
"""

import json
from openai import OpenAI

from core.types import AgentResponse, TaskResult, TaskStatus, DecisionType
from core.state import ExecutionState
from core.config import Config
from tools.registry import ToolRegistry
from tools.cli_tool import CLITool
from tools.file_tool import FileTool
from tools.system_tool import SystemTool
from planner.planner import TaskPlanner
from planner.validator import PlanValidator
from executor.executor import TaskExecutor
from agents.main_agent.router import Router
from agents.main_agent.prompts import REPLY_SYSTEM_PROMPT


class MainAgent:
    """
    The CEO of the agent system.
    
    Usage:
        agent = MainAgent()
        response = agent.handle("List all Python files in the current directory")
    """

    def __init__(self, enable_browser: bool = None, enable_vision: bool = None):
        # Config
        self.config = Config
        issues = Config.validate()
        if issues:
            print(f"⚠️ Config issues: {issues}")

        # Shared state (persists across tasks within a session)
        self.state = ExecutionState()

        # Tool registry — register all available tools
        self.registry = ToolRegistry()
        self._register_tools(enable_browser, enable_vision)

        # Planner
        self.planner = TaskPlanner(self.registry)

        # Validator
        self.validator = PlanValidator(self.registry)

        # Executor
        self.executor = TaskExecutor(
            self.registry,
            self.planner,
            on_step_complete=self._on_step_complete,
            on_replan=self._on_replan,
        )

        # Router
        self.router = Router()

        # LLM client for simple replies
        provider = Config.get_provider()
        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "nvidia":
            base_url = "https://integrate.api.nvidia.com/v1"
        else:
            base_url = "https://openrouter.ai/api/v1"
        self.reply_client = OpenAI(base_url=base_url, api_key=Config.get_api_key())

        print(f"\n🤖 EvilAgent MainAgent initialized")
        print(f"   {Config.summary()}")
        print(f"   Tools: {self.registry.list_names()}")

    def _register_tools(self, enable_browser: bool = None, enable_vision: bool = None):
        """Register all available tools."""
        # Always available
        self.registry.register(CLITool())
        self.registry.register(FileTool())
        self.registry.register(SystemTool())

        # LLM intelligence tool — processes/cleans/summarizes text
        from tools.llm_tool import LLMTool
        self.registry.register(LLMTool())

        # Conditional tools
        if enable_browser if enable_browser is not None else Config.ENABLE_BROWSER:
            try:
                from tools.browser_tool import BrowserTool
                self.registry.register(BrowserTool(
                    api_key=Config.get_api_key(),
                    headless=False,
                ))
            except Exception as e:
                print(f"⚠️ Browser tool not available: {e}")

        if enable_vision if enable_vision is not None else Config.ENABLE_VISION:
            try:
                from tools.vision_tool import VisionTool
                self.registry.register(VisionTool())
            except Exception as e:
                print(f"⚠️ Vision tool not available: {e}")

    # ─── Main Entry Point ───────────────────────────────────────

    def handle(self, user_input: str) -> AgentResponse:
        """
        Handle any user input — the single entry point.
        
        Args:
            user_input: Raw user input (could be a task or a question)
        
        Returns:
            AgentResponse with message, task result, and/or state snapshot
        """
        print(f"\n{'═'*60}")
        print(f"📥 Input: {user_input}")
        print(f"{'═'*60}")

        # Step 1: Route — is this a task or a simple question?
        decision = self.router.classify(user_input)
        print(f"🔀 Router: {decision.type.value} (confidence={decision.confidence:.2f})")
        if decision.reasoning:
            print(f"   💭 {decision.reasoning}")

        if decision.type == DecisionType.SIMPLE_REPLY:
            # Simple conversational reply
            reply = self._generate_reply(user_input)
            return AgentResponse(message=reply)

        # Step 2: Plan — decompose into steps
        goal = decision.extracted_goal or user_input
        print(f"\n📋 Planning: {goal}")

        try:
            plan = self.planner.plan(goal, self.state)
        except Exception as e:
            return AgentResponse(
                message=f"❌ Planning failed: {str(e)}",
                task_result=TaskResult(status=TaskStatus.FAILED, error=str(e)),
            )

        # Display the plan
        print(f"\n📋 Plan ({len(plan)} steps):")
        for step in plan:
            print(f"   {step.id}. [{step.tool}] {step.action}: {step.description}")

        # Step 3: Validate the plan
        validation = self.validator.validate(plan)
        if not validation["valid"]:
            print(f"\n⚠️ Plan validation issues:")
            for issue in validation["issues"]:
                print(f"   ❌ Step {issue['step_id']}: {issue['error']}")

            # Try to get planner to fix the plan (one attempt)
            try:
                issues_text = self.validator.format_issues(validation)
                print("🔧 Asking planner to fix the plan...")
                plan = self.planner.plan(
                    f"{goal}\n\nPREVIOUS PLAN HAD ERRORS:\n{issues_text}\n\nFix these issues and generate a corrected plan.",
                    self.state,
                )
                # Re-validate
                validation = self.validator.validate(plan)
                if not validation["valid"]:
                    return AgentResponse(
                        message=f"❌ Plan validation failed even after fix attempt",
                        task_result=TaskResult(status=TaskStatus.FAILED, error="Plan validation failed"),
                    )
            except Exception as e:
                return AgentResponse(
                    message=f"❌ Plan fix failed: {str(e)}",
                    task_result=TaskResult(status=TaskStatus.FAILED, error=str(e)),
                )

        # Step 4: Execute
        result = self.executor.run(plan, self.state, goal=goal)

        # Step 5: Build response
        message = self._build_result_message(goal, result)

        return AgentResponse(
            message=message,
            task_result=result,
            state_snapshot=self.state.snapshot(),
        )

    # ─── Reply Generation ───────────────────────────────────────

    def _generate_reply(self, user_input: str) -> str:
        """Generate a conversational reply for non-task inputs."""
        try:
            completion = self.reply_client.chat.completions.create(
                model=Config.REPLY_MODEL,
                messages=[
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.7,
                max_tokens=1024,
                stream=True,
            )

            reply = ""
            for chunk in completion:
                if not getattr(chunk, "choices", None):
                    continue
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    reply += chunk.choices[0].delta.content

            return reply or "I couldn't generate a response. Please try again."

        except Exception as e:
            return f"I'd help you with that, but encountered an error: {str(e)}"

    # ─── Result Summary ─────────────────────────────────────────

    def _build_result_message(self, goal: str, result: TaskResult) -> str:
        """Build a human-readable result summary."""
        if result.status == TaskStatus.SUCCESS:
            msg = f"✅ Task completed: {goal}"
            msg += f"\n   Steps: {result.steps_completed}/{result.steps_total}"
            if result.replans > 0:
                msg += f" (replanned {result.replans}x)"

            # Include last output if available
            last_output = self.state.get("last_output")
            if last_output:
                output_str = str(last_output)[:500]
                msg += f"\n\n📤 Output:\n{output_str}"

            return msg

        elif result.status == TaskStatus.FAILED:
            msg = f"❌ Task failed: {goal}"
            msg += f"\n   Completed: {result.steps_completed}/{result.steps_total}"
            if result.error:
                msg += f"\n   Error: {result.error}"
            return msg

        else:
            return f"⚠️ Task ended with status: {result.status.value}"

    # ─── Progress Callbacks ─────────────────────────────────────

    def _on_step_complete(self, step, result, state):
        """Called after each step completes (for UI updates)."""
        pass  # Can be wired to websocket for real-time updates

    def _on_replan(self, failed_step, new_plan, state):
        """Called when replanning occurs."""
        pass  # Can be wired to websocket

    # ─── Session Management ─────────────────────────────────────

    def reset(self):
        """Reset state for a new task (but keep tools registered)."""
        self.state.reset()

    def close(self):
        """Cleanup all resources."""
        if self.registry.has("browser"):
            try:
                tool = self.registry.get("browser")
                if hasattr(tool, "close"):
                    tool.close()
            except Exception:
                pass
