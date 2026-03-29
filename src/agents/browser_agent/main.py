"""
Browser Agent — standalone entry point.
Run: python3 -m agents.browser_agent.main
"""

import os
import asyncio
from dotenv import load_dotenv
from agents.browser_agent.loop import BrowserAgent

# Load .env from src/ directory
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


async def main():
    API_KEY = os.environ.get("NVIDIA_API_KEY")

    if not API_KEY:
        print("❌ NVIDIA_API_KEY not found in .env")
        return

    # Optional: path to credentials.json
    creds_path = os.path.join(os.path.dirname(__file__), "..", "..", "credentials.json")
    if not os.path.exists(creds_path):
        creds_path = None

    agent = BrowserAgent(
        api_key=API_KEY,
        headless=False,  # visible browser
        credentials_path=creds_path,
    )

    print("🌐 EvilAgent Browser Agent")
    print("=" * 40)

    goal = input("Enter goal: ").strip()
    if not goal:
        print("❌ No goal provided")
        return

    start_url = input("Start URL (press Enter to skip): ").strip() or None

    result = await agent.run(goal=goal, start_url=start_url)

    print(f"\n{'='*40}")
    print(f"📊 Result: {result}")

    # Keep browser open until user decides to close
    print("\n🌐 Browser is still open. Press Enter to close it...")
    input()
    await agent.close()
    print("🌐 Browser closed.")


if __name__ == "__main__":
    asyncio.run(main())
