from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

DECISION_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action_type": {
            "type": "string",
            "enum": ["move", "talk", "work", "rest"],
        },
        "target_location_id": {"type": ["string", "null"]},
        "target_agent_id": {"type": ["string", "null"]},
        "message": {
            "type": ["string", "null"],
            "description": "发言内容（仅 talk 类型需要；talk 在执行层会映射为 speech 事件）",
        },
        "payload": {"type": ["object", "null"]},
    },
    "required": ["action_type"],
    "additionalProperties": False,
}


class RuntimeDecision(BaseModel):
    action_type: str
    target_location_id: str | None = None
    target_agent_id: str | None = None
    message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload(cls, values: Any) -> Any:
        if isinstance(values, dict) and values.get("payload") is None:
            values["payload"] = {}
        return values


def build_decision_prompt(prompt: str) -> str:
    json_schema = json.dumps(DECISION_OUTPUT_SCHEMA, indent=2)
    return f"""{prompt}

重要：你必须只返回一个有效的 JSON 对象，不要有其他任何文本。JSON 格式如下:
{json_schema}

返回 JSON，不要有 markdown 代码块标记。"""


def clean_response_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```json?\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    return cleaned.strip()


def parse_runtime_decision(text: str) -> RuntimeDecision:
    cleaned = clean_response_text(text)
    try:
        return RuntimeDecision.model_validate_json(cleaned)
    except Exception:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = cleaned[start : end + 1]
            try:
                return RuntimeDecision.model_validate_json(json_str)
            except (json.JSONDecodeError, ValidationError) as exc:
                msg = f"Failed to parse decision JSON: {exc}"
                raise RuntimeError(msg) from exc
        raise ValueError("No valid JSON found in response")
