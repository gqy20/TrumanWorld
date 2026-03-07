from __future__ import annotations

import json
from pathlib import Path


class PromptLoader:
    """Loads prompt.md and prepares prompt text for runtime use."""

    def load(self, path: Path) -> str:
        return path.read_text(encoding="utf-8").strip()

    def render(self, base_prompt: str, context: dict[str, object] | None = None) -> str:
        if not context:
            return base_prompt

        lines = [base_prompt, "", "# 运行上下文", "```json", self._to_pretty_json(context), "```"]
        return "\n".join(lines)

    def render_decision_prompt(
        self,
        base_prompt: str,
        context: dict[str, object],
        allowed_actions: list[str],
    ) -> str:
        lines = [
            base_prompt,
            "",
            "# 决策任务",
            "你必须基于当前上下文为该 agent 生成下一步动作意图。",
            f"允许的动作只有：{', '.join(allowed_actions)}。",
            "",
            "# 输出约束",
            "- 只能返回一个 JSON 对象",
            "- JSON 仅可包含字段：`action_type`、`target_location_id`、`target_agent_id`、`payload`",
            "- `action_type` 必须来自允许动作集合",
            "- 当 `action_type=move` 时，应尽量提供 `target_location_id`",
            "- 当 `action_type=talk` 时，应尽量提供 `target_agent_id`",
            "- 如果信息不足，优先返回 `rest` 或 `work`，不要编造不存在的地点和人物",
            "",
            "# 运行上下文",
            "```json",
            self._to_pretty_json(context),
            "```",
        ]
        return "\n".join(lines)

    def _to_pretty_json(self, payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
