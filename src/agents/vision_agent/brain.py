"""
Vision Brain — multimodal LLM integration for the vision agent.
Uses NVIDIA API with moonshotai/kimi-k2.5 model for vision understanding.
"""

import json
import requests
import time
from typing import Optional, Tuple
from agents.vision_agent.prompt import SYSTEM_PROMPT, VERIFICATION_PROMPT


class VisionBrain:
    """
    Multimodal LLM interface — sends screenshots as inline base64 images
    to NVIDIA's API and returns structured JSON actions.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "moonshotai/kimi-k2.5",
        temperature: float = 0.1,
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.url = "https://integrate.api.nvidia.com/v1/chat/completions"

    def think(
        self,
        screenshot_b64: str,
        goal: str,
        memory: str,
        screen_size: Tuple[int, int] = (1920, 1080),
        max_retries: int = 3,
    ) -> str:
        """
        Send screenshot + context to VLM and get an action response.

        Args:
            screenshot_b64: Base64-encoded JPEG screenshot
            goal: The user's high-level goal
            memory: Formatted action history
            screen_size: (width, height) of the screenshot
            max_retries: Number of retry attempts

        Returns:
            Raw LLM response text (should be JSON)
        """
        user_content = self._build_user_message(
            screenshot_b64, goal, memory, screen_size
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return self._call_llm(messages, max_retries)

    def verify(
        self,
        before_b64: str,
        after_b64: str,
        action_description: str,
        max_retries: int = 2,
    ) -> str:
        """
        Send before/after screenshots to verify if an action succeeded.

        Args:
            before_b64: Screenshot before action
            after_b64: Screenshot after action
            action_description: Human-readable description of what was done
            max_retries: Number of retry attempts

        Returns:
            Raw LLM response text (should be verification JSON)
        """
        prompt_text = VERIFICATION_PROMPT.format(
            action_description=action_description
        )

        # NVIDIA format: inline <img> tags in the message content
        content = (
            f"{prompt_text}\n\n"
            f'BEFORE screenshot:\n<img src="data:image/jpeg;base64,{before_b64}" />\n\n'
            f'AFTER screenshot:\n<img src="data:image/jpeg;base64,{after_b64}" />'
        )

        messages = [{"role": "user", "content": content}]

        return self._call_llm(messages, max_retries)

    def _build_user_message(
        self,
        screenshot_b64: str,
        goal: str,
        memory: str,
        screen_size: Tuple[int, int],
    ) -> str:
        """Build the user message with inline base64 image (NVIDIA format)."""
        text_parts = f"Goal: {goal}\n"
        text_parts += f"Screen resolution: {screen_size[0]}x{screen_size[1]}\n\n"

        if memory and memory != "(no previous actions)":
            text_parts += f"Previous Actions:\n{memory}\n\n"

        text_parts += "Current screen state is shown in the image below. Decide the next action.\n\n"

        # NVIDIA API format: inline <img> tag with base64 data
        text_parts += f'<img src="data:image/jpeg;base64,{screenshot_b64}" />'

        return text_parts

    def _call_llm(self, messages: list, max_retries: int) -> str:
        """Make the actual API call with retry logic."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096,
            "temperature": self.temperature,
            "top_p": 1.00,
            "stream": False,
            # Disable reasoning mode for speed
            "chat_template_kwargs": {"thinking": False},
        }

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.url,
                    headers=headers,
                    json=payload,
                    timeout=90,  # vision requests can take longer
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                if response.status_code == 429 and attempt < max_retries - 1:
                    wait = (attempt + 1) * 5
                    print(f"⏳ Rate limited, retrying in {wait}s...")
                    time.sleep(wait)
                    continue

                raise Exception(
                    f"VLM Error ({response.status_code}): {response.text[:300]}"
                )

            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"⏳ Request timed out, retrying...")
                    time.sleep(3)
                    continue
                raise Exception("VLM request timed out after all retries")

            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    print(f"⏳ Connection error, retrying...")
                    time.sleep(3)
                    continue
                raise Exception("Cannot connect to NVIDIA API")
