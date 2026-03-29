"""
Response Parser — extracts and validates structured JSON from VLM output.
Handles bbox validation, coordinate centering, and action-specific field checks.
"""

import json
import re
from typing import Tuple, Optional


def parse_response(text: str, screen_size: Tuple[int, int] = (1920, 1080)) -> dict:
    """
    Extract and validate JSON from VLM response text.

    Args:
        text: Raw LLM response string
        screen_size: (width, height) for coordinate bounds checking

    Returns:
        Validated action dict or error dict
    """
    try:
        # Try to find JSON in code blocks first
        code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if code_block:
            return _validate(json.loads(code_block.group(1)), screen_size)

        # Find the first { ... } block
        start = text.find("{")
        end = text.rfind("}") + 1

        if start == -1 or end == 0:
            return _error("No JSON found in VLM response", text)

        json_str = text[start:end]
        data = json.loads(json_str)
        return _validate(data, screen_size)

    except json.JSONDecodeError as e:
        return _error(f"Invalid JSON: {e}", text)
    except Exception as e:
        return _error(f"Parse error: {e}", text)


def _validate(data: dict, screen_size: Tuple[int, int]) -> dict:
    """Validate the parsed action structure and compute click coordinates."""
    w, h = screen_size

    # Check for completion/error status
    if data.get("status") in ("done", "error"):
        return data

    # Must have an action
    action = data.get("action", "").lower()
    if not action:
        return _error("Missing 'action' field", str(data))

    data["action"] = action

    # Extract and validate confidence
    confidence = data.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (ValueError, TypeError):
        confidence = 0.0
    data["confidence"] = max(0.0, min(1.0, confidence))

    # Validate per action type
    if action in ("click", "double_click", "right_click"):
        if "bbox" not in data:
            return _error(f"{action} requires 'bbox' [x1, y1, x2, y2]", str(data))
        bbox = _validate_bbox(data["bbox"], w, h)
        if bbox is None:
            return _error(f"Invalid bbox: {data['bbox']}", str(data))
        data["bbox"] = bbox
        data["click_x"], data["click_y"] = _bbox_center(bbox)

    elif action == "type":
        if "text" not in data:
            return _error("type requires 'text'", str(data))

    elif action == "hotkey":
        if "keys" not in data or not isinstance(data["keys"], list):
            return _error("hotkey requires 'keys' list", str(data))
        if len(data["keys"]) == 0:
            return _error("hotkey 'keys' list is empty", str(data))

    elif action == "scroll":
        data.setdefault("direction", "down")
        data.setdefault("amount", 3)
        if "bbox" in data:
            bbox = _validate_bbox(data["bbox"], w, h)
            if bbox:
                data["bbox"] = bbox
                data["scroll_x"], data["scroll_y"] = _bbox_center(bbox)

    elif action == "drag":
        if "from_bbox" not in data or "to_bbox" not in data:
            return _error("drag requires 'from_bbox' and 'to_bbox'", str(data))
        from_bbox = _validate_bbox(data["from_bbox"], w, h)
        to_bbox = _validate_bbox(data["to_bbox"], w, h)
        if from_bbox is None or to_bbox is None:
            return _error("Invalid from_bbox or to_bbox", str(data))
        data["from_bbox"] = from_bbox
        data["to_bbox"] = to_bbox
        data["from_x"], data["from_y"] = _bbox_center(from_bbox)
        data["to_x"], data["to_y"] = _bbox_center(to_bbox)

    elif action == "wait":
        data.setdefault("seconds", 2)
        try:
            data["seconds"] = min(max(0.5, float(data["seconds"])), 10.0)
        except (ValueError, TypeError):
            data["seconds"] = 2

    else:
        return _error(f"Unknown action: {action}", str(data))

    return data


def _validate_bbox(
    bbox, max_w: int, max_h: int
) -> Optional[Tuple[int, int, int, int]]:
    """
    Validate and clamp a bounding box to screen dimensions.

    Args:
        bbox: Raw bbox value (should be [x1, y1, x2, y2])
        max_w: Maximum screen width
        max_h: Maximum screen height

    Returns:
        Clamped (x1, y1, x2, y2) tuple or None if invalid
    """
    try:
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None

        x1, y1, x2, y2 = [int(v) for v in bbox]

        # Clamp to screen bounds
        x1 = max(0, min(x1, max_w))
        y1 = max(0, min(y1, max_h))
        x2 = max(0, min(x2, max_w))
        y2 = max(0, min(y2, max_h))

        # Ensure valid rectangle (x2 > x1, y2 > y1)
        if x2 <= x1 or y2 <= y1:
            return None

        return (x1, y1, x2, y2)
    except (ValueError, TypeError):
        return None


def _bbox_center(bbox: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """Compute the center point of a bounding box."""
    x1, y1, x2, y2 = bbox
    return (x1 + x2) // 2, (y1 + y2) // 2


def _error(reason: str, raw: str) -> dict:
    """Return a standardized error response."""
    return {
        "status": "error",
        "reason": reason,
        "raw": raw[:500],
    }
