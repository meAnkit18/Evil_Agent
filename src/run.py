"""
Standalone CLI entry point for the agent system.

Usage:
    cd src/
    python3 -m run                          # Interactive mode
    python3 -m run "list all python files"  # Direct goal mode

This is the fastest way to test the agent.
"""

import os
import sys

# Ensure src/ is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Config


def main():
    print("=" * 60)
    print("🤖 EvilAgent — Production Agent System")
    print("   main_agent → planner → executor → tools")
    print("=" * 60)

    # Validate config
    issues = Config.validate()
    if issues:
        for issue in issues:
            print(f"❌ {issue}")
        sys.exit(1)

    # Import here to defer heavy initialization
    from agents.main_agent.agent import MainAgent

    agent = MainAgent(
        enable_browser=Config.ENABLE_BROWSER,
        enable_vision=Config.ENABLE_VISION,
    )

    # Check if goal was passed as CLI argument
    if len(sys.argv) > 1:
        goal = " ".join(sys.argv[1:])
        print(f"\n🎯 Goal: {goal}")
        response = agent.handle(goal)
        print(f"\n{'═'*60}")
        print(response.message)
        return

    # Interactive REPL mode
    print("\n📝 Enter your goal (or 'quit' to exit)")
    print("   Examples:")
    print("   - list all python files in current directory")
    print("   - create a hello.py file with a print statement")
    print("   - what is the current OS version?")
    print()

    while True:
        try:
            user_input = input("🎯 > ").strip()

            if not user_input:
                continue

            if user_input.lower() in ("quit", "exit", "q"):
                print("👋 Bye!")
                break

            if user_input.lower() == "reset":
                agent.reset()
                print("🔄 State reset")
                continue

            if user_input.lower() == "state":
                print(agent.state.format_for_llm())
                continue

            if user_input.lower() == "tools":
                print(agent.registry.format_for_llm())
                continue

            response = agent.handle(user_input)
            print(f"\n{'─'*60}")
            print(response.message)
            print(f"{'─'*60}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted. Bye!")
            break

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    agent.close()


if __name__ == "__main__":
    main()
