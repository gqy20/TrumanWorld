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
        action_names = ", ".join(allowed_actions)
        lines = [
            base_prompt,
            "",
            "# 决策任务",
            "基于你的角色和上述对话历史，决定下一步动作。",
            "优先保持当前情境一致，不要因为不确定就默认选择 work 或 rest。",
            "不要把普通停留、等待、整理或在家活动表述成 `work`。",
            f"本场景允许的动作类型：{action_names}。",
            "",
            "## 上下文使用原则",
            "- 根据 world.daily_schedule 与 world.time_period 主动执行当前时段计划",
            "- 存在 world.pending_reply 时，若对方仍在附近，优先延续对话",
            "- 使用 world.conversation_state 和 conversation_diagnostics 推进话题，避免重复",
            "- recent_events 按事件历史理解，只引入与当前决策相关的信息",
            "",
            "## 标准动作",
            "- move: 移动到指定地点（需提供 target_location_id，使用真实存在的地点 ID）",
            "- talk: 与附近的 agent 对话（需提供 target_agent_id 和 message，30-200 字自然发言）",
            "- work: 在当前地点工作（仅在合理工作场景中使用）",
            "- rest: 休息/等待/日常活动",
            "",
            "## 自由动作（可选）",
            "除了标准动作，你还可以执行任何合理的社会行为。",
            "当标准动作无法表达你的意图时，可以选择自由动作：",
            "- trade: 与他人交易物品（需 target_agent_id，payload 包含 item、price）",
            "- gift: 赠送物品给他人（需 target_agent_id，payload 包含 item）",
            "- craft: 制作物品（payload 包含 item、materials）",
            "- open_business: 开店经营（payload 包含 type、investment、location）",
            "- lend: 借出物品或钱款（需 target_agent_id，payload 包含 item 或 amount）",
            "- negotiate: 协商/议价（需 target_agent_id，payload 包含 topic、proposal）",
            "",
            "自由动作示例：",
            """```json
{
  "action_type": "trade",
  "target_agent_id": "alice",
  "payload": {
    "item": "coffee",
    "price": 30,
    "quantity": 1
  },
  "raw_intent": "我想从 Alice 那买一杯咖啡，价格 30 元"
}
```""",
            "",
            "# 输出约束",
            "- 只能返回一个 JSON 对象",
            "- 标准动作 JSON 仅可包含字段：`action_type`、`target_location_id`、`target_agent_id`、`message`、`payload`",
            "- JSON 仅可包含字段：`action_type`、`target_location_id`、`target_agent_id`、`message`、`payload`、`raw_intent`、`plan_update`（可选）",
            "- 标准动作优先使用标准类型（move/talk/work/rest）",
            "- 当 `action_type=move` 时，只能使用运行上下文中真实存在的地点 ID，不要编造别名、英文变体或不存在的地点",
            "- 当 `action_type=talk` 时，必须提供 `target_agent_id` 与 `message`（30-200 字的自然发言；会在执行层映射为 speech 事件）",
            "- 自由动作必须通过 `payload` 提供完整参数，并通过 `raw_intent` 描述你的意图",
            "- 选择最符合角色、日程和当前情境的低风险动作；仅在确实没有合理动作时返回 `rest`",
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
            "# 动态决策上下文",
            *self._render_decision_context_hints(context),
            "",
            "# 运行上下文",
            "```json",
            self._to_pretty_json(context),
            "```",
        ]
        return "\n".join(lines)

    @staticmethod
    def _render_decision_context_hints(context: dict[str, object]) -> list[str]:
        world = context.get("world")
        if not isinstance(world, dict):
            return []

        lines: list[str] = []
        pending_reply = world.get("pending_reply")
        if isinstance(pending_reply, dict):
            lines.extend(
                [
                    "# 待回应对话",
                    "有人刚刚直接对你说话。如果对方还在附近，优先延续这段对话。",
                    f"- 发言人: {pending_reply.get('from_agent_name', '对方')}",
                    f"- 优先级: {pending_reply.get('priority', 'medium')}",
                ]
            )
            message = pending_reply.get("message")
            if isinstance(message, str) and message:
                lines.append(f'- 对方刚才说: "{message}"')
            lines.append("")

        diagnostics = world.get("conversation_diagnostics")
        if isinstance(diagnostics, dict):
            lines.extend(["# 当前对话判断线索", "用这些线索推进话题，不要机械重复上一句。"])
            fields = (
                ("conversation_focus", "当前话题"),
                ("other_party_latest_new_info", "对方上一轮新增信息"),
                ("other_party_latest_intent", "对方最近意图"),
                ("conversation_phase", "当前阶段"),
                ("unresolved_item", "仍待处理的问题"),
            )
            for key, label in fields:
                value = diagnostics.get(key)
                if isinstance(value, str) and value:
                    lines.append(f"- {label}: {value}")
            repetition = diagnostics.get("self_recent_repetition")
            if isinstance(repetition, dict) and repetition.get("is_repeating") is True:
                repeat_type = repetition.get("type") or "表达"
                repeat_span = repetition.get("repeat_span")
                suffix = f"（连续 {repeat_span} 轮）" if isinstance(repeat_span, int) else ""
                lines.append(f"- 你最近可能在重复: {repeat_type}{suffix}")

        return lines

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
