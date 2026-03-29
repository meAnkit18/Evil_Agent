"""
LLM Tool — text intelligence layer.

This is the BRAIN tool. When raw data comes out of browser/CLI extraction,
this tool processes it with LLM to extract meaning, summarize, clean, or answer questions.

Without this, the agent dumps raw DOM text into files.
With this, it can: extract only relevant stats, summarize articles, clean HTML noise, etc.
"""

from openai import OpenAI
from tools.base import BaseTool
from core.types import ToolResult
from core.state import ExecutionState
from core.config import Config


class LLMTool(BaseTool):
    name = "llm"
    description = (
        "Process text with AI intelligence — summarize, extract specific info, "
        "clean noisy data, answer questions about text, reformat content. "
        "Best for: cleaning raw web page text, extracting specific data from noisy output, "
        "summarizing long content, reformatting data into clean structure."
    )
    actions = ["summarize", "extract_info", "clean_text", "answer", "reformat"]

    def __init__(self):
        api_key = Config.get_api_key()
        provider = Config.get_provider()

        if provider == "groq":
            base_url = "https://api.groq.com/openai/v1"
        elif provider == "nvidia":
            base_url = "https://integrate.api.nvidia.com/v1"
        else:
            base_url = "https://openrouter.ai/api/v1"

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = Config.REPLY_MODEL

    def execute(self, action: str, args: dict, state: ExecutionState) -> ToolResult:
        try:
            if action == "summarize":
                return self._summarize(args, state)
            elif action == "extract_info":
                return self._extract_info(args, state)
            elif action == "clean_text":
                return self._clean_text(args, state)
            elif action == "answer":
                return self._answer(args, state)
            elif action == "reformat":
                return self._reformat(args, state)
            else:
                return ToolResult.error(f"Unknown LLM action: {action}")
        except Exception as e:
            return ToolResult.fail(f"LLM tool error: {str(e)}", retryable=True)

    def validate(self, action: str, args: dict) -> tuple[bool, str]:
        valid, err = super().validate(action, args)
        if not valid:
            return valid, err

        if action in ("summarize", "clean_text") and "text" not in args:
            return False, "Missing required arg: 'text'"
        if action == "extract_info" and ("text" not in args or "query" not in args):
            return False, "Missing required args: 'text' and 'query'"
        if action == "answer" and ("text" not in args or "question" not in args):
            return False, "Missing required args: 'text' and 'question'"
        if action == "reformat" and ("text" not in args or "format" not in args):
            return False, "Missing required args: 'text' and 'format'"

        return True, ""

    # ─── Actions ─────────────────────────────────────────────────

    def _summarize(self, args: dict, state: ExecutionState) -> ToolResult:
        text = args["text"]
        max_length = args.get("max_length", 500)

        result = self._call_llm(
            f"Summarize the following text concisely in under {max_length} characters. "
            f"Keep only the most important facts and data:\n\n{text[:8000]}"
        )

        return ToolResult.success(
            result=result,
            message=f"Summarized to {len(result)} chars",
            state_update={"last_output": result},
        )

    def _extract_info(self, args: dict, state: ExecutionState) -> ToolResult:
        text = args["text"]
        query = args["query"]

        result = self._call_llm(
            f"From the following text, extract ONLY the information relevant to: {query}\n\n"
            f"Rules:\n"
            f"- Return ONLY the extracted data, no explanations\n"
            f"- Format it cleanly and readably\n"
            f"- If the information is not found, say 'Not found'\n"
            f"- Remove all navigation text, ads, and irrelevant content\n\n"
            f"Text:\n{text[:8000]}"
        )

        return ToolResult.success(
            result=result,
            message=f"Extracted info ({len(result)} chars)",
            state_update={"last_output": result},
        )

    def _clean_text(self, args: dict, state: ExecutionState) -> ToolResult:
        text = args["text"]

        result = self._call_llm(
            f"Clean up the following raw text extracted from a web page.\n\n"
            f"Rules:\n"
            f"- Remove navigation menus, ads, footers, and UI elements\n"
            f"- Keep only the main content\n"
            f"- Format it cleanly with proper line breaks\n"
            f"- Preserve all data, statistics, and factual information\n\n"
            f"Raw text:\n{text[:8000]}"
        )

        return ToolResult.success(
            result=result,
            message=f"Cleaned to {len(result)} chars",
            state_update={"last_output": result},
        )

    def _answer(self, args: dict, state: ExecutionState) -> ToolResult:
        text = args["text"]
        question = args["question"]

        result = self._call_llm(
            f"Based on the following text, answer this question: {question}\n\n"
            f"Text:\n{text[:8000]}"
        )

        return ToolResult.success(
            result=result,
            message=f"Answer: {result[:100]}",
            state_update={"last_output": result},
        )

    def _reformat(self, args: dict, state: ExecutionState) -> ToolResult:
        text = args["text"]
        target_format = args["format"]

        result = self._call_llm(
            f"Reformat the following text into this format: {target_format}\n\n"
            f"Text:\n{text[:8000]}"
        )

        return ToolResult.success(
            result=result,
            message=f"Reformatted ({len(result)} chars)",
            state_update={"last_output": result},
        )

    # ─── LLM Call ────────────────────────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a precise data extraction and text processing assistant. Follow instructions exactly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4096,
            stream=True,
        )

        result = ""
        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue
            if chunk.choices and chunk.choices[0].delta.content is not None:
                result += chunk.choices[0].delta.content

        return result.strip()
