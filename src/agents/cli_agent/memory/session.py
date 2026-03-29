from typing import List, Dict


class SessionMemory:
    def __init__(self, max_steps: int = 5):
        self.history: List[Dict] = []
        self.max_steps = max_steps

    def add(self, command: str, output: str, status: str):
        self.history.append({
            "command": command,
            "output": output[-1000:],  # truncate to avoid token explosion
            "status": status
        })

        if len(self.history) > self.max_steps:
            self.history.pop(0)

    def get_context(self) -> List[Dict]:
        return self.history

    def format_for_llm(self) -> str:
        formatted = ""
        for step in self.history:
            formatted += f"\nCommand: {step['command']}\nStatus: {step['status']}\nOutput: {step['output']}\n"
        return formatted.strip()