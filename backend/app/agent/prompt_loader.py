from __future__ import annotations

import json
import re
from pathlib import Path

PLANNER_PROMPT_PATH = Path(__file__).with_name("prompts") / "planner.md"
REFLECTOR_PROMPT_PATH = Path(__file__).with_name("prompts") / "reflector.md"


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
        ]

        # 渲染日程引导（如果有 daily_schedule）
        # daily_schedule 在 context["world"] 子字典中（由 build_agent_world_context 注入）
        _world_ctx = context.get("world") or {}
        daily_schedule = _world_ctx.get("daily_schedule") if isinstance(_world_ctx, dict) else None
        time_period = _world_ctx.get("time_period") if isinstance(_world_ctx, dict) else None
        if daily_schedule and isinstance(daily_schedule, dict):
            lines.append("# 我的日程计划")
            lines.append(
                "以下是我今天的日程安排。我应当主动根据当前时间段选择符合计划的行为，不要仅仅因为不确定就选 rest。"
            )
            lines.append("")
            period_label = {
                "dawn": "黎明",
                "morning": "上午",
                "daytime": "白天",
                "noon": "中午",
                "afternoon": "下午",
                "evening": "傍晚",
                "night": "夜间",
            }
            for key in ("morning", "daytime", "evening"):
                val = daily_schedule.get(key)
                if val:
                    period_zh = period_label.get(key, key)
                    # 直接显示原始文本，不再查字典翻译
                    is_current = (
                        (key == "morning" and time_period in {"dawn", "morning"})
                        or (key == "daytime" and time_period in {"noon", "afternoon"})
                        or (key == "evening" and time_period == "evening")
                    )
                    marker = " (← 当前时段)" if is_current else ""
                    lines.append(f"- {period_zh}: {val}{marker}")
            lines.append("")

        # 渲染对话历史（如果有）
        recent_events = context.get("recent_events", [])
        if recent_events:
            lines.append("# 最近对话")
            lines.append(
                "以下是最近发生的事件（按时间倒序）。你需要延续这些对话，而不是重复或忽略。"
            )
            lines.append("")
            for evt in reversed(recent_events):  # 按时间正序显示
                lines.append(self._format_event(evt))
            lines.append("")

        lines.extend(
            [
                "# 决策任务",
                "基于你的角色和上述对话历史，决定下一步动作。",
                f"允许的动作只有：{', '.join(allowed_actions)}。",
                "",
                "# 输出约束",
                "- 只能返回一个 JSON 对象",
                "- JSON 仅可包含字段：`action_type`、`target_location_id`、`target_agent_id`、`message`、`payload`、`plan_update`（可选）",
                "- `action_type` 必须来自允许动作集合",
                "- 当 `action_type=move` 时，应尽量提供 `target_location_id`",
                "- 当 `action_type=move` 时，只能使用运行上下文中真实存在的地点 ID，不要编造别名、英文变体或不存在的地点",
                "- 当 `action_type=talk` 时，必须提供 `target_agent_id` 与 `message`（30-200 字的自然发言；会在执行层映射为 speech 事件）",
                "- 如果信息不足，优先保持当前情境一致，通常返回 `rest`，不要把普通停留、等待、整理或在家活动表述成 `work`",
                "- 只有当你明确处在合理的工作场景中时，才返回 `work`；有固定工作地点的人在到达工作地点前应优先 `move` 或 `rest`",
                "- **重要**：对话要延续之前的内容，不要重复已说过的话",
                "",
                "# 计划更新（可选）",
                "如果遇到以下情况，可以考虑更新今日计划：",
                "- 遇到了重要的人，想多交流",
                "- 突发世界事件（如停电、活动、广播）",
                "- 有意外的社交机会",
                "如果需要更新计划，在 JSON 中添加 `plan_update` 字段：",
                """```json
{
  "action_type": "talk",
  "target_agent_id": "bob",
  "message": "嗨 Bob!",
  "plan_update": {
    "reason": "遇到重要的人",
    "new_daytime": "和 Bob 聊天"
  }
}
```""",
                "",
                "# 运行上下文",
                "```json",
                self._to_pretty_json(context),
                "```",
            ]
        )
        return "\n".join(lines)

    def _format_event(self, evt: dict[str, object]) -> str:
        """格式化单个事件为可读文本"""
        event_type = evt.get("event_type", "unknown")
        actor_name = evt.get("actor_name", "某人")
        target_name = evt.get("target_name", "")
        tick_no = evt.get("tick_no", "?")

        if event_type in {"talk", "speech"}:
            message = evt.get("message", "...")
            if target_name:
                return f'[Tick {tick_no}] {actor_name} → {target_name}: "{message}"'
            return f'[Tick {tick_no}] {actor_name}: "{message}"'
        elif event_type == "listen":
            if target_name:
                return f"[Tick {tick_no}] {actor_name} 正在听 {target_name} 说话"
            return f"[Tick {tick_no}] {actor_name} 正在倾听"
        elif event_type == "conversation_started":
            if target_name:
                return f"[Tick {tick_no}] {actor_name} 与 {target_name} 开始了一段对话"
            return f"[Tick {tick_no}] {actor_name} 开始了一段对话"
        elif event_type == "conversation_joined":
            if target_name:
                return f"[Tick {tick_no}] {actor_name} 加入了 {target_name} 主导的对话"
            return f"[Tick {tick_no}] {actor_name} 加入了一段对话"
        elif event_type == "move":
            location = evt.get("location_name", "某地")
            return f"[Tick {tick_no}] {actor_name} 移动到了 {location}"
        elif event_type == "work":
            return f"[Tick {tick_no}] {actor_name} 正在工作"
        elif event_type == "rest":
            return f"[Tick {tick_no}] {actor_name} 正在休息"
        else:
            return f"[Tick {tick_no}] {actor_name} 执行了 {event_type}"

    def render_planner_prompt(self, agent_name: str, context: dict[str, object]) -> str:
        """Render the daily planning prompt for a given agent."""
        base = PLANNER_PROMPT_PATH.read_text(encoding="utf-8").strip()
        base = base.replace("{agent_name}", agent_name)
        lines = [base, ""]

        # 如果有昨日计划执行情况，单独展示
        yesterday_execution = context.get("yesterday_plan_execution")
        if yesterday_execution:
            lines.extend(
                [
                    "# 昨日计划执行情况",
                    yesterday_execution,
                    "",
                ]
            )

        # 近期记忆
        recent_memories = context.get("recent_memories", [])
        if recent_memories:
            lines.extend(
                [
                    "# 近期记忆",
                    "以下是你近期记得的一些事情：",
                    "",
                ]
            )
            for mem in recent_memories[-3:]:  # 只显示最近3条
                content = mem.get("content", "")[:100]
                if content:
                    lines.append(f"- {content}")
            lines.append("")

        lines.extend(
            [
                "# 运行上下文",
                "```json",
                self._to_pretty_json(context),
                "```",
            ]
        )
        return "\n".join(lines)

    def render_reflector_prompt(
        self,
        agent_name: str,
        context: dict[str, object],
        daily_events: list[dict[str, object]],
    ) -> str:
        """Render the daily reflection prompt for a given agent."""
        base = REFLECTOR_PROMPT_PATH.read_text(encoding="utf-8").strip()
        base = base.replace("{agent_name}", agent_name)
        lines = [base, ""]
        if daily_events:
            lines.append("# 今日事件回顾")
            lines.append("以下是今天发生的事情：")
            lines.append("")
            for evt in daily_events:
                lines.append(self._format_event(evt))
            lines.append("")
        lines.extend(
            [
                "# 运行上下文",
                "```json",
                self._to_pretty_json(context),
                "```",
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def extract_json_from_text(text: str) -> dict | None:
        """Extract the first JSON object from LLM text output."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```json?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    return None
        return None

    def _to_pretty_json(self, payload: dict[str, object]) -> str:
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str)
