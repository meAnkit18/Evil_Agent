"""
Response Parser — extracts and validates structured JSON from LLM output.
Mirrors the CLI agent parser pattern with browser-specific validation.
"""

import json
import re


def parse_response(text: str) -> dict:
    """
    Extract JSON from LLM response text.
    Handles markdown code blocks, extra text around JSON, etc.
    """
    try:
        # Try to find JSON in code blocks first
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            return _validate(json.loads(code_block.group(1)))

        # Find the first { ... } block
        start = text.find("{")
        end = text.rfind("}") + 1

        if start == -1 or end == 0:
            return _error("No JSON found in LLM response", text)

        json_str = text[start:end]
        data = json.loads(json_str)
        return _validate(data)

    except json.JSONDecodeError as e:
        return _error(f"Invalid JSON: {e}", text)
    except Exception as e:
        return _error(f"Parse error: {e}", text)


def _validate(data: dict) -> dict:
    """Validate the parsed action structure."""

    # Check for completion/error status
    if data.get("status") in ("done", "error"):
        return data

    # Must have an action
    action = data.get("action", "").lower()
    if not action:
        return _error("Missing 'action' field", str(data))

    # Normalize
    data["action"] = action

    # Validate required fields per action
    if action == "click":
        if "element_id" not in data:
            return _error("click requires 'element_id'", str(data))
        data["element_id"] = int(data["element_id"])

    elif action == "type":
        if "element_id" not in data:
            return _error("type requires 'element_id'", str(data))
        if "text" not in data:
            return _error("type requires 'text'", str(data))
        data["element_id"] = int(data["element_id"])

    elif action == "navigate":
        if "url" not in data:
            return _error("navigate requires 'url'", str(data))

    elif action == "scroll":
        data.setdefault("direction", "down")

    elif action == "wait":
        data.setdefault("seconds", 2)

    elif action == "select":
        if "element_id" not in data:
            return _error("select requires 'element_id'", str(data))
        if "value" not in data:
            return _error("select requires 'value'", str(data))
        data["element_id"] = int(data["element_id"])

    else:
        return _error(f"Unknown action: {action}", str(data))

    return data


def _error(reason: str, raw: str) -> dict:
    """Return a standardized error response."""
    return {
        "status": "error",
        "reason": reason,
        "raw": raw[:500]
    }
