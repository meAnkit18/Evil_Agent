import requests
import time
from agents.cli_agent.prompt import SYSTEM_PROMPT


class Brain:
    def __init__(self, api_key: str, model: str = "openrouter/free"):
        self.api_key = api_key
        self.model = model
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def think(self, goal: str, memory: str, max_retries: int = 3) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Goal: {goal}\n\nPrevious steps:\n{memory}"
            }
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        for attempt in range(max_retries):
            response = requests.post(self.url, headers=headers, json=payload)

            if response.status_code == 200:
                return response.json()["choices"][0]["message"]["content"]

            # Retry on rate limits (429)
            if response.status_code == 429 and attempt < max_retries - 1:
                wait = (attempt + 1) * 5
                print(f"⏳ Rate limited, retrying in {wait}s...")
                time.sleep(wait)
                continue

            raise Exception(f"LLM Error ({response.status_code}): {response.text}")