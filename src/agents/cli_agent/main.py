import os
from dotenv import load_dotenv
from agents.cli_agent.loop import CLIAgent

# Load .env from the src/ directory (main.py is at src/agents/cli_agent/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


if __name__ == "__main__":
    API_KEY = os.environ.get("OPENROUTER_API_KEY")

    if not API_KEY:
        print("❌ OPENROUTER_API_KEY not found in .env")
        exit(1)

    agent = CLIAgent(api_key=API_KEY)

    try:
        goal = input("Enter goal: ")
        agent.run(goal)
    finally:
        agent.close()