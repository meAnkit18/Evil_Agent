from agents.cli_agent.terminal.pty_terminal import PTYTerminal
from agents.cli_agent.terminal.guard import CommandGuard
from agents.cli_agent.memory.session import SessionMemory
from agents.cli_agent.parser import parse_response
from agents.cli_agent.brain import Brain
from agents.cli_agent.terminal.executor import CommandExecutor


class CLIAgent:
    def __init__(self, api_key: str):
        self.terminal = PTYTerminal()
        self.guard = CommandGuard()
        self.memory = SessionMemory()
        self.brain = Brain(api_key)
        self.executor = CommandExecutor(self.terminal, self.guard)

    def run(self, goal: str, max_steps: int = 20):
        print(f"\n🎯 Goal: {goal}\n")

        for step in range(max_steps):
            print(f"\n--- Step {step + 1} ---")

            # Step 1: prepare memory context
            memory_context = self.memory.format_for_llm()

            # Step 2: LLM thinking
            response = self.brain.think(goal, memory_context)
            parsed = parse_response(response)

            print("🧠 LLM:", parsed)

            # Step 3: check completion
            if parsed.get("status") == "done":
                print("\n✅ Task completed")
                return

            if parsed.get("status") == "error":
                print("\n❌ Failed:", parsed.get("reason"))
                return

            # Step 4: get command
            command = parsed.get("command")

            if not command:
                print("\n❌ No command received from LLM")
                return

            # Step 5: execute via executor (includes guard)
            result = self.executor.execute(command)

            # Step 6: handle execution result
            if result["status"] == "blocked":
                print(f"\n🚫 Blocked command: {command}")
                return

            if result["status"] == "error":
                print(f"\n❌ Execution error: {result['error']}")

            print("💻 Output:\n", result["output"])

            # Step 7: store memory
            self.memory.add(command, result["output"], result["status"])

        print("\n⚠️ Max steps reached without completion")

    def close(self):
        self.terminal.close()