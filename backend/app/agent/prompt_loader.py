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

        pending_reply = _world_ctx.get("pending_reply") if isinstance(_world_ctx, dict) else None
        if pending_reply and isinstance(pending_reply, dict):
            from_agent_name = pending_reply.get("from_agent_name", "对方")
            message = pending_reply.get("message", "")
            priority = pending_reply.get("priority", "medium")
            lines.append("# 待回应对话")
            lines.append(
                "有人刚刚直接对你说话。如果对方还在附近，优先延续这段对话，不要无故转去 rest。"
            )
            lines.append(f"- 发言人: {from_agent_name}")
            lines.append(f"- 优先级: {priority}")
            if isinstance(message, str) and message:
                lines.append(f'- 对方刚才说: "{message}"')
            lines.append("")

        conversation_state = (
            _world_ctx.get("conversation_state") if isinstance(_world_ctx, dict) else None
        )
        if conversation_state and isinstance(conversation_state, dict):
            lines.append("# 当前对话状态")
            lines.append("如果还在延续同一段对话，请优先推进内容，不要重复上一轮的提议。")
            repeat_count = conversation_state.get("repeat_count")
            if isinstance(repeat_count, int):
                lines.append(f"- 当前重复次数: {repeat_count}")
            last_proposal = conversation_state.get("last_proposal")
            if isinstance(last_proposal, str) and last_proposal:
                lines.append(f'- 最近提议: "{last_proposal}"')
            open_question = conversation_state.get("open_question")
            if isinstance(open_question, str) and open_question:
                lines.append(f'- 待回应问题: "{open_question}"')
            lines.append("")

        conversation_diagnostics = (
            _world_ctx.get("conversation_diagnostics") if isinstance(_world_ctx, dict) else None
        )
        if conversation_diagnostics and isinstance(conversation_diagnostics, dict):
            lines.append("# 当前对话判断线索")
            lines.append("这些线索用于帮助你判断对话下一步该推进什么，而不是机械重复上一句。")
            conversation_focus = conversation_diagnostics.get("conversation_focus")
            if isinstance(conversation_focus, str) and conversation_focus:
                lines.append(f"- 当前话题: {conversation_focus}")
            latest_new_info = conversation_diagnostics.get("other_party_latest_new_info")
            if isinstance(latest_new_info, str) and latest_new_info:
                lines.append(f"- 对方上一轮新增信息: {latest_new_info}")
            latest_intent = conversation_diagnostics.get("other_party_latest_intent")
            if isinstance(latest_intent, str) and latest_intent:
                lines.append(f"- 对方最近意图: {latest_intent}")
            conversation_phase = conversation_diagnostics.get("conversation_phase")
            if isinstance(conversation_phase, str) and conversation_phase:
                lines.append(f"- 当前阶段: {conversation_phase}")
            repetition = conversation_diagnostics.get("self_recent_repetition")
            if isinstance(repetition, dict) and repetition.get("is_repeating") is True:
                repeat_type = repetition.get("type") or "表达"
                repeat_span = repetition.get("repeat_span")
                if isinstance(repeat_span, int) and repeat_span > 0:
                    lines.append(f"- 你最近可能在重复: {repeat_type}（连续 {repeat_span} 轮）")
                else:
                    lines.append(f"- 你最近可能在重复: {repeat_type}")
            unresolved_item = conversation_diagnostics.get("unresolved_item")
            if isinstance(unresolved_item, str) and unresolved_item:
                lines.append(f"- 仍待处理的问题: {unresolved_item}")
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
                "- JSON 仅可包含字段：`action_type`、`target_location_id`、`target_agent_id`、`message`、`payload`、`raw_intent`、`plan_update`（可选）",
                "- 标准动作优先使用标准类型（move/talk/work/rest）",
                "- 当 `action_type=move` 时，只能使用运行上下文中真实存在的地点 ID，不要编造别名、英文变体或不存在的地点",
                "- 当 `action_type=talk` 时，必须提供 `target_agent_id` 与 `message`",
                "- 自由动作必须通过 `payload` 提供完整参数，并通过 `raw_intent` 描述你的意图",
                "- 如果信息不足或不确定，优先返回 `rest`",
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
