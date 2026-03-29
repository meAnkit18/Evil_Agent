"""
Browser Agent Loop — the core observe → think → act → repeat engine.
This is the heart of the browser agent.
"""

import asyncio
from agents.browser_agent.browser.controller import BrowserController
from agents.browser_agent.browser.dom_processor import DOMProcessor
from agents.browser_agent.browser.element_indexer import ElementIndexer
from agents.browser_agent.browser.actions import ActionEngine
from agents.browser_agent.browser.state import capture_state
from agents.browser_agent.browser.guard import BrowserGuard
from agents.browser_agent.browser.session import CredentialManager
from agents.browser_agent.memory.session import SessionMemory
from agents.browser_agent.brain import Brain
from agents.browser_agent.parser import parse_response


class BrowserAgent:
    """
    Stateful, perception-driven browser execution engine.
    Controlled by an LLM through structured action commands.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-oss-120b",
        headless: bool = False,
        credentials_path: str = None,
    ):
        # Browser stack
        self.controller = BrowserController(headless=headless)
        self.dom_processor = DOMProcessor()
        self.indexer = ElementIndexer()
        self.guard = BrowserGuard()
        self.credential_manager = CredentialManager(credentials_path)

        # LLM stack
        self.brain = Brain(api_key=api_key, model=model)

        # Memory
        self.memory = SessionMemory(max_steps=8)

        # Action engine (initialized per-run with credentials)
        self.action_engine = None

    async def run(self, goal: str, start_url: str = None, max_steps: int = 15):
        """
        Execute the observe → think → act loop.

        Args:
            goal: The user's high-level goal (e.g., "Log in to GitHub")
            start_url: Optional starting URL
            max_steps: Maximum iterations before stopping
        """
        print(f"\n🎯 Goal: {goal}")
        print(f"🔄 Max steps: {max_steps}\n")

        # Launch browser
        await self.controller.launch()

        # Set up credentials for current site
        site_creds = {}
        if start_url:
            site_creds = self.credential_manager.get_for_site(start_url)

        self.action_engine = ActionEngine(
            controller=self.controller,
            indexer=self.indexer,
            credentials=site_creds,
        )

        # Navigate to start URL if provided
        if start_url:
            await self.controller.navigate(start_url)

        try:
            consecutive_errors = 0

            for step in range(1, max_steps + 1):
                print(f"\n{'='*50}")
                print(f"--- Step {step}/{max_steps} ---")

                # ═══ OBSERVE ═══
                print("👁️ Observing page...")
                state = await capture_state(
                    self.controller, self.dom_processor, self.indexer
                )
                print(f"   📍 URL: {state.url}")
                print(f"   🧩 Elements found: {state.element_count}")

                # ═══ THINK ═══
                print("🧠 Thinking...")
                memory_context = self.memory.format_for_llm()
                page_context = state.format_for_llm()

                try:
                    llm_response = self.brain.think(
                        goal=goal,
                        page_state=page_context,
                        memory=memory_context,
                    )
                    consecutive_errors = 0
                except Exception as e:
                    print(f"❌ LLM Error: {e}")
                    return {"status": "llm_error", "error": str(e), "steps": step}

                # ═══ PARSE ═══
                parsed = parse_response(llm_response)
                thought = parsed.get("thought", "")
                if thought:
                    print(f"   💭 {thought}")

                # Check for completion
                if parsed.get("status") == "done":
                    print("\n✅ Task completed!")
                    print(f"   💭 {thought}")
                    return {"status": "done", "steps": step, "url": state.url}

                if parsed.get("status") == "error":
                    reason = parsed.get("reason", "Unknown error")
                    print(f"\n❌ Task failed: {reason}")
                    return {"status": "error", "reason": reason, "steps": step}

                # Check for parse errors
                action_type = parsed.get("action")
                if not action_type:
                    print(f"⚠️ No valid action parsed: {parsed.get('reason', 'unknown')}")
                    # Record as failed step so LLM knows
                    self.memory.add(step, {"action": "parse_error"}, {
                        "status": "error",
                        "message": parsed.get("reason", "No action parsed"),
                    })
                    continue

                # ═══ GUARD ═══
                guard_result = self.guard.check_action(parsed)
                if guard_result["status"] == "blocked":
                    print(f"🚫 Action blocked: {guard_result['reason']}")
                    self.memory.add(step, parsed, {
                        "status": "blocked",
                        "message": guard_result["reason"],
                    })
                    continue

                # ═══ ACT ═══
                print(f"⚡ Executing: {action_type}", end="")
                if "element_id" in parsed:
                    print(f" [element {parsed['element_id']}]", end="")
                print()

                # Update credentials if URL changed
                current_url = self.controller.current_url()
                if current_url:
                    new_creds = self.credential_manager.get_for_site(current_url)
                    if new_creds:
                        self.action_engine.credentials = new_creds

                result = await self.action_engine.execute(parsed)
                print(f"   → {result['status']}: {result.get('message', '')}")

                # ═══ RECORD ═══
                self.memory.add(step, parsed, result)

            print(f"\n⚠️ Max steps ({max_steps}) reached without completion")
            return {"status": "max_steps", "steps": max_steps}

        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted by user")
            return {"status": "interrupted"}

        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            return {"status": "fatal_error", "error": str(e)}

    async def close(self):
        """Cleanup browser resources."""
        await self.controller.close()
        self.memory.clear()
