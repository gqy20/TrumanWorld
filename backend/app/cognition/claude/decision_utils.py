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
            "description": (
                "动作类型。标准动作：move（移动）、talk（对话）、work（工作）、rest（休息）。"
                "自由动作：trade（交易）、gift（赠送）、craft（制作）、open_business（开店）等。"
                "自由动作必须通过 payload 提供完整参数。"
            ),
        },
        "target_location_id": {"type": ["string", "null"]},
        "target_agent_id": {"type": ["string", "null"]},
        "message": {
            "type": ["string", "null"],
            "description": "发言内容（仅 talk 类型需要；talk 在执行层会映射为 speech 事件）",
        },
        "payload": {
            "type": ["object", "null"],
            "description": (
                "动作参数。标准动作：空对象或 {}。自由动作必须提供完整参数，"
                "如 trade 需要 {item, price, quantity}，gift 需要 {item}。"
            ),
        },
        "raw_intent": {
            "type": ["string", "null"],
            "description": "原始意图描述（仅自由动作使用，用于记录 agent 想做什么）",
        },
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
    raw_intent: str | None = None

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


def _extract_first_json_object(text: str) -> str | None:
    decoder = json.JSONDecoder()
    search_from = 0

    while True:
        start = text.find("{", search_from)
        if start == -1:
            return None
        try:
            obj, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            search_from = start + 1
            continue
        if isinstance(obj, dict):
            return text[start:end]
        search_from = start + 1


def parse_runtime_decision(text: str) -> RuntimeDecision:
    cleaned = clean_response_text(text)
    try:
        return RuntimeDecision.model_validate_json(cleaned)
    except Exception:
        json_str = _extract_first_json_object(cleaned)
        if json_str is not None:
            try:
                return RuntimeDecision.model_validate_json(json_str)
            except (json.JSONDecodeError, ValidationError) as exc:
                msg = f"Failed to parse decision JSON: {exc}"
                raise RuntimeError(msg) from exc
        raise ValueError("No valid JSON found in response")
