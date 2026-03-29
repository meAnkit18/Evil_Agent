"""
Router — intent classification: is this a task or a simple question?

Uses rule-based fast-path for obvious cases, falls back to LLM for ambiguous inputs.
"""

import json
from openai import OpenAI

from core.types import AgentDecision, DecisionType
from core.config import Config
from planner.prompts import ROUTER_PROMPT


class Router:
    """
    Classifies user input as TASK (needs execution) or SIMPLE_REPLY (just chat).
    
    Strategy:
    1. Rule-based fast path — catches 80% of inputs without an LLM call
    2. LLM fallback — for ambiguous cases
    """

    # Keywords that strongly signal a task
    TASK_KEYWORDS = [
        "open", "create", "make", "build", "run", "execute", "download",
        "install", "delete", "remove", "find", "search", "list", "show",
        "move", "copy", "rename", "update", "deploy", "start", "stop",
        "navigate", "click", "type", "scroll", "browse", "go to",
        "write", "save", "edit", "modify", "change", "fix",
        "setup", "configure", "set up", "check", "test", "verify",
        "get", "fetch", "scrape", "extract", "upload",
    ]

    # Keywords that signal a question/conversation
    QUESTION_KEYWORDS = [
        "what is", "what are", "how does", "how do", "why is", "why do",
        "explain", "tell me about", "define", "meaning of",
        "difference between", "compare", "vs",
        "can you explain", "help me understand",
    ]

    def __init__(self, api_key: str = "", model: str = ""):
        self.api_key = api_key or Config.get_api_key()
        self.model = model or Config.ROUTER_MODEL

        provider = Config.get_provider()
        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "nvidia":
            base_url = "https://integrate.api.nvidia.com/v1"
        else:
            base_url = "https://openrouter.ai/api/v1"

        self.client = OpenAI(base_url=base_url, api_key=self.api_key)

    def classify(self, user_input: str) -> AgentDecision:
        """
        Classify user input as task or simple reply.
        
        Returns:
            AgentDecision with type, confidence, and extracted goal
        """
        # Step 1: Rule-based fast path
        decision = self._rule_based(user_input)
        if decision and decision.confidence >= 0.8:
            return decision

        # Step 2: LLM fallback for ambiguous cases
        try:
            return self._llm_classify(user_input)
        except Exception as e:
            # If LLM fails, default to task (safer — better to over-execute than under-execute)
            print(f"⚠️ Router LLM failed: {e}, defaulting to TASK")
            return AgentDecision(
                type=DecisionType.TASK,
                confidence=0.5,
                extracted_goal=user_input,
                reasoning="LLM classification failed, defaulting to task",
            )

    def _rule_based(self, text: str) -> AgentDecision | None:
        """Fast rule-based classification."""
        lower = text.lower().strip()

        # Very short inputs are usually questions
        if len(lower) < 5:
            return AgentDecision(
                type=DecisionType.SIMPLE_REPLY,
                confidence=0.7,
                reasoning="Very short input",
            )

        # Check for task keywords at the start
        for keyword in self.TASK_KEYWORDS:
            if lower.startswith(keyword) or f" {keyword} " in f" {lower} ":
                return AgentDecision(
                    type=DecisionType.TASK,
                    confidence=0.85,
                    extracted_goal=text,
                    reasoning=f"Task keyword detected: '{keyword}'",
                )

        # Check for question patterns
        for keyword in self.QUESTION_KEYWORDS:
            if lower.startswith(keyword):
                return AgentDecision(
                    type=DecisionType.SIMPLE_REPLY,
                    confidence=0.85,
                    reasoning=f"Question pattern detected: '{keyword}'",
                )

        # Questions ending with "?"
        if lower.endswith("?") and not any(k in lower for k in ["can you", "could you", "would you"]):
            return AgentDecision(
                type=DecisionType.SIMPLE_REPLY,
                confidence=0.7,
                reasoning="Question mark detected",
            )

        # "can you X" / "could you X" are usually tasks
        if any(lower.startswith(p) for p in ["can you", "could you", "would you", "please"]):
            return AgentDecision(
                type=DecisionType.TASK,
                confidence=0.8,
                extracted_goal=text,
                reasoning="Polite request pattern",
            )

        return None  # Ambiguous — let LLM decide

    def _llm_classify(self, user_input: str) -> AgentDecision:
        """Use LLM for ambiguous cases."""
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": ROUTER_PROMPT},
                {"role": "user", "content": user_input},
            ],
            temperature=0.1,
            max_tokens=256,
            stream=True,
        )

        # Collect streamed response
        content = ""
        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue
            if chunk.choices and chunk.choices[0].delta.content is not None:
                content += chunk.choices[0].delta.content

        if not content:
            raise Exception("Empty response from router LLM")

        # Parse the JSON response
        try:
            text = content.strip()
            # Extract JSON object
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]

            data = json.loads(text)

            decision_type = DecisionType.TASK if data.get("type") == "task" else DecisionType.SIMPLE_REPLY

            return AgentDecision(
                type=decision_type,
                confidence=float(data.get("confidence", 0.5)),
                extracted_goal=data.get("extracted_goal", user_input) if decision_type == DecisionType.TASK else "",
                reasoning=data.get("reasoning", ""),
            )

        except (json.JSONDecodeError, KeyError):
            # Parse failed — default to task
            return AgentDecision(
                type=DecisionType.TASK,
                confidence=0.5,
                extracted_goal=user_input,
                reasoning="Router parse failed, defaulting to task",
            )

