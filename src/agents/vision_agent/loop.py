"""
Vision Agent Loop — the core perceive → reason → act → verify engine.
This is the heart of the vision agent.
"""

import time
from typing import Optional, Dict

from agents.vision_agent.screen import ScreenCapture
from agents.vision_agent.brain import VisionBrain
from agents.vision_agent.parser import parse_response
from agents.vision_agent.planner import ActionPlanner
from agents.vision_agent.executor import ScreenExecutor
from agents.vision_agent.guard import VisionGuard
from agents.vision_agent.feedback import FeedbackLoop
from agents.vision_agent.memory.session import SessionMemory
from agents.vision_agent.memory.spatial import SpatialMemory


class VisionAgent:
    """
    Pixel-based desktop automation agent.
    Operates any application through screenshot perception + mouse/keyboard control.

    Architecture:
        PERCEIVE → REASON → PLAN → GUARD → EXECUTE → VERIFY → RECORD → LOOP
    """

    def __init__(
        self,
        api_key: str,
        model: str = "google/gemini-2.0-flash-exp:free",
        monitor: int = 0,
        max_width: int = 1920,
        max_height: int = 1080,
        confidence_threshold: float = 0.5,
        vlm_verify: bool = True,
        move_duration: float = 0.3,
    ):
        """
        Args:
            api_key: OpenRouter API key
            model: Vision-capable model name
            monitor: Monitor index (0 = all, 1 = primary)
            max_width: Max screenshot width (downscales for speed/cost)
            max_height: Max screenshot height
            confidence_threshold: Minimum VLM confidence to execute
            vlm_verify: Enable VLM-based post-action verification
            move_duration: Mouse movement speed
        """
        # Perception
        self.screen = ScreenCapture(
            monitor=monitor,
            max_width=max_width,
            max_height=max_height,
        )

        # Reasoning
        self.brain = VisionBrain(api_key=api_key, model=model)

        # Decision
        self.planner = ActionPlanner(confidence_threshold=confidence_threshold)

        # Execution
        self.executor = ScreenExecutor(move_duration=move_duration)

        # Safety
        self.guard = VisionGuard()

        # Verification
        self.feedback = FeedbackLoop(
            brain=self.brain if vlm_verify else None,
            vlm_verify=vlm_verify,
        )

        # Memory
        self.memory = SessionMemory(max_steps=10)
        self.spatial = SpatialMemory()

        # Config
        self.vlm_verify = vlm_verify
        self._running = False

    def run(self, goal: str, max_steps: int = 25) -> Dict:
        """
        Execute the perception → reasoning → action → verification loop.

        Args:
            goal: The user's high-level goal (e.g., "Open the Downloads folder")
            max_steps: Maximum iterations before stopping

        Returns:
            Result dict with status, steps taken, etc.
        """
        print(f"\n🎯 Goal: {goal}")
        print(f"🔄 Max steps: {max_steps}")
        print(f"🖥️  Screen: {self.screen.screen_size}")
        print(f"🤖 Model: {self.brain.model}")
        print(f"🔍 VLM verify: {self.vlm_verify}\n")

        self._running = True
        consecutive_errors = 0
        max_consecutive_errors = 5
        retry_count = 0
        max_retries_per_step = 2

        try:
            for step in range(1, max_steps + 1):
                if not self._running:
                    return {"status": "cancelled", "steps": step - 1}

                print(f"\n{'='*60}")
                print(f"--- Step {step}/{max_steps} ---")

                # ═══════════════════════════════
                # 1. PERCEIVE — capture screenshot
                # ═══════════════════════════════
                print("👁️  Capturing screen...")
                before_img = self.screen.capture_full()
                before_b64, screen_size = self.screen.to_base64(before_img), before_img.size

                # Update spatial memory resolution
                self.spatial.update_resolution(screen_size[0], screen_size[1])

                print(f"   📐 Resolution: {screen_size[0]}x{screen_size[1]}")

                # ═══════════════════════════════
                # 2. REASON — send to VLM
                # ═══════════════════════════════
                print("🧠 Reasoning...")
                memory_context = self.memory.format_for_llm()
                spatial_context = self.spatial.format_for_llm()

                # Combine memory + spatial for context
                full_context = memory_context
                if spatial_context:
                    full_context += f"\n\n{spatial_context}"

                try:
                    llm_response = self.brain.think(
                        screenshot_b64=before_b64,
                        goal=goal,
                        memory=full_context,
                        screen_size=screen_size,
                    )
                    consecutive_errors = 0
                except Exception as e:
                    print(f"❌ VLM Error: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        return {
                            "status": "vlm_error",
                            "error": str(e),
                            "steps": step,
                        }
                    continue

                # ═══════════════════════════════
                # 3. PARSE — extract structured action
                # ═══════════════════════════════
                parsed = parse_response(llm_response, screen_size)
                reasoning = parsed.get("reasoning", parsed.get("thought", ""))
                if reasoning:
                    print(f"   💭 {reasoning[:150]}")

                # Check for completion
                if parsed.get("status") == "done":
                    print("\n✅ Task completed!")
                    return {"status": "done", "steps": step}

                if parsed.get("status") == "error" and "action" not in parsed:
                    reason = parsed.get("reason", "Unknown error")
                    print(f"\n❌ Task failed: {reason}")
                    return {"status": "error", "reason": reason, "steps": step}

                # ═══════════════════════════════
                # 4. PLAN — evaluate action
                # ═══════════════════════════════
                evaluation = self.planner.evaluate(parsed)
                decision = evaluation["decision"]

                if decision == "retry":
                    print(f"🔄 Retry: {evaluation['reason']}")
                    retry_count += 1
                    if retry_count >= max_retries_per_step:
                        retry_count = 0
                        self.memory.add(step, parsed, {
                            "status": "skipped",
                            "message": evaluation["reason"],
                        })
                    continue

                if decision == "reject":
                    print(f"⛔ Rejected: {evaluation['reason']}")
                    self.memory.add(step, parsed, {
                        "status": "rejected",
                        "message": evaluation["reason"],
                    })
                    continue

                retry_count = 0
                action = evaluation["action"]
                action_type = action.get("action", action.get("status", ""))

                # ═══════════════════════════════
                # 5. GUARD — safety check
                # ═══════════════════════════════
                guard_result = self.guard.check_action(action)
                if guard_result["status"] == "blocked":
                    print(f"🚫 Blocked: {guard_result['reason']}")
                    self.memory.add(step, action, {
                        "status": "blocked",
                        "message": guard_result["reason"],
                    })
                    continue

                # ═══════════════════════════════
                # 6. EXECUTE — perform the action
                # ═══════════════════════════════
                target = action.get("target", "")
                conf = action.get("confidence", 0.0)
                print(f"⚡ Executing: {action_type}", end="")
                if "click_x" in action:
                    print(f" at ({action['click_x']}, {action['click_y']})", end="")
                if target:
                    print(f" → '{target}'", end="")
                print(f" [conf={conf:.2f}]")

                result = self.executor.execute(action)
                print(f"   → {result['status']}: {result.get('message', '')}")

                # ═══════════════════════════════
                # 7. VERIFY — post-action feedback
                # ═══════════════════════════════
                verification = None
                if action_type not in ("wait",):
                    print("🔍 Verifying...")
                    time.sleep(0.5)  # wait for UI to update

                    after_img = self.screen.capture_full()
                    after_b64 = self.screen.to_base64(after_img)

                    v_result = self.feedback.verify_action(
                        before_img=before_img,
                        after_img=after_img,
                        action=action,
                        before_b64=before_b64 if self.vlm_verify else None,
                        after_b64=after_b64 if self.vlm_verify else None,
                    )

                    verification = v_result.to_dict()
                    v_icon = "✓" if v_result.success else "✗"
                    print(f"   {v_icon} Verified: {v_result.evidence}")

                    # Update planner tracking
                    if v_result.success:
                        self.planner.record_success(action)
                    else:
                        self.planner.record_failure(action)

                # ═══════════════════════════════
                # 8. RECORD — update memory
                # ═══════════════════════════════
                self.memory.add(step, action, result, verification)

                # Update spatial memory if we clicked something with a name
                if "bbox" in action and target:
                    self.spatial.record(
                        name=target,
                        bbox=action["bbox"],
                        confidence=conf,
                    )

            # Exhausted max steps
            print(f"\n⚠️ Max steps ({max_steps}) reached without completion")
            return {"status": "max_steps", "steps": max_steps}

        except KeyboardInterrupt:
            print("\n\n🛑 Interrupted by user")
            return {"status": "interrupted"}

        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "fatal_error", "error": str(e)}

        finally:
            self.close()

    def stop(self):
        """Signal the agent to stop after the current step."""
        self._running = False

    def close(self):
        """Cleanup resources."""
        self.screen.close()
        self.memory.clear()
        self.spatial.clear()
        self.planner.reset()
        self.guard.reset()
