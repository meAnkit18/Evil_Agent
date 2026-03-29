#!/usr/bin/env python3
"""Quick test script for the CLI agent."""
import os
import sys

# Ensure we can import from src/
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from agents.cli_agent.loop import CLIAgent

API_KEY = os.environ.get("OPENROUTER_API_KEY")
if not API_KEY:
    print("❌ OPENROUTER_API_KEY not set")
    sys.exit(1)

print(f"✅ API key loaded (ends with ...{API_KEY[-6:]})")
print("🚀 Starting CLI Agent test...\n")

agent = CLIAgent(api_key=API_KEY)

try:
    agent.run("List the files in the current directory", max_steps=5)
finally:
    agent.close()

print("\n🏁 Test complete.")
