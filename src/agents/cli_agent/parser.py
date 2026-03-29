import json


def parse_response(text: str) -> dict:
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        json_str = text[start:end]

        data = json.loads(json_str)
        return data

    except Exception:
        return {
            "status": "error",
            "reason": "Invalid JSON from LLM",
            "raw": text
        }