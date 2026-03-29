"""
Vision Agent — standalone entry point.
Run: python3 -m agents.vision_agent.main
"""

import os
import sys
from dotenv import load_dotenv
from agents.vision_agent.loop import VisionAgent

# Load .env from src/ directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


def main():
    # Try NVIDIA key first, then OpenRouter
    API_KEY = os.environ.get("NVIDIA_API_KEY") or os.environ.get("OPENROUTER_API_KEY")

    if not API_KEY:
        print("❌ NVIDIA_API_KEY not found in .env")
        print("   Add: NVIDIA_API_KEY=nvapi-...")
        return

    print("=" * 60)
    print("👁️  EvilAgent Vision Agent")
    print("   Pixel-based desktop automation — operates like a human")
    print("=" * 60)
    print()

    # Configuration
    model = os.environ.get(
        "VISION_MODEL", "moonshotai/kimi-k2.5"
    )
    monitor = int(os.environ.get("VISION_MONITOR", "0"))
    verify = os.environ.get("VISION_VERIFY", "true").lower() == "true"

    print(f"🤖 Model:   {model}")
    print(f"🖥️  Monitor: {monitor}")
    print(f"🔍 Verify:  {verify}")
    print()

    agent = VisionAgent(
        api_key=API_KEY,
        model=model,
        monitor=monitor,
        vlm_verify=verify,
        confidence_threshold=0.5,
    )

    print(f"📐 Screen:  {agent.screen.screen_size}")
    print()

    # Get goal from user
    goal = input("🎯 Enter goal: ").strip()
    if not goal:
        print("❌ No goal provided")
        return

    # Optional: max steps
    max_steps_input = input("🔄 Max steps (default 25): ").strip()
    max_steps = int(max_steps_input) if max_steps_input else 25

    print(f"\n⚠️  SAFETY: Move mouse to any screen corner to abort (pyautogui failsafe)")
    print(f"⚠️  Press Ctrl+C to interrupt\n")

    # Run the agent
    result = agent.run(goal=goal, max_steps=max_steps)

    print(f"\n{'='*60}")
    print(f"📊 Final Result:")
    for k, v in result.items():
        print(f"   {k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
