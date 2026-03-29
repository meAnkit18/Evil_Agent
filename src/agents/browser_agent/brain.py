"""
Brain — LLM integration for the browser agent.
Sends page state + history to NVIDIA API and gets structured actions back.
Uses OpenAI SDK with streaming for reliable responses.
"""

import time
from openai import OpenAI
from agents.browser_agent.prompt import SYSTEM_PROMPT


class Brain:
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b"):
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
        )

    def think(self, goal: str, page_state: str, memory: str, max_retries: int = 3) -> str:
        """
        Send the current context to the LLM and get an action response.

        Args:
            goal: The user's high-level goal
            page_state: Formatted page state (URL, elements, text)
            memory: Formatted action history
            max_retries: Number of retry attempts on failure
        """
        user_content = f"Goal: {goal}\n\n"

        if memory:
            user_content += f"Previous Actions:\n{memory}\n\n"

        user_content += f"Current Page State:\n{page_state}"

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        for attempt in range(max_retries):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=1,
                    top_p=1,
                    max_tokens=4096,
                    stream=True,
                )

                # Collect streamed response
                full_response = ""
                for chunk in completion:
                    if not getattr(chunk, "choices", None):
                        continue
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content

                if full_response:
                    return full_response

                raise Exception("Empty response from NVIDIA API")

            except Exception as e:
                error_msg = str(e)

                # Rate limit — back off and retry
                if "429" in error_msg and attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    print(f"⏳ Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                # Timeout / connection errors — retry
                if ("timeout" in error_msg.lower() or "connection" in error_msg.lower()) and attempt < max_retries - 1:
                    print(f"⏳ Connection issue, retrying...")
                    time.sleep(3)
                    continue

                # Final attempt or unrecoverable error
                if attempt >= max_retries - 1:
                    raise Exception(f"NVIDIA API error after {max_retries} attempts: {error_msg}")

                raise
