"""LLM-based consequence generator for free actions."""

from __future__ import annotations

import json

from app.cognition.claude.free_text_utils import run_text_query
from app.infra.logging import get_logger
from app.sim.state_delta_models import (
    AgentDelta,
    MemoryFragment,
    RelationshipDelta,
    StateDelta,
    WorldDelta,
)

logger = get_logger(__name__)


# Template for consequence generation prompt
CONSEQUENCE_PROMPT_TEMPLATE = """你是后果生成器。根据动作和当前世界状态，生成该动作造成的状态变更。

## 动作信息
- 动作类型: {action_type}
- 执行者: {agent_id}
- 目标 agent: {target_agent_id}
- 目标地点: {target_location_id}
- 原始意图: {raw_intent}
- 动作参数: {payload}

## 执行者 ({agent_id}) 经济状态
- 现金: {actor_cash}
- 就业状态: {actor_employment}
- 食物安全: {actor_food_security}

## 目标 agent ({target_agent_id}) 经济状态
- 现金: {target_cash}
- 就业状态: {target_employment}
- 食物安全: {target_food_security}

## 规则评估结果
{matched_rules}

## 输出格式 (JSON)
返回以下格式的 JSON，不要有其他任何文字：
{{
  "agent_deltas": {{
    "<agent_id>": {{
      "cash_delta": 0.0,
      "food_security_delta": 0.0,
      "inventory_add": [],
      "inventory_remove": [],
      "employment_status": null
    }}
  }},
  "relationship_deltas": {{
    "<agent1_id>:<agent2_id>": {{
      "familiarity_delta": 0.0,
      "trust_delta": 0.0,
      "affinity_delta": 0.0
    }}
  }},
  "memory_fragments": [
    {{"agent_id": "<id>", "content": "发生了什么"}}
  ],
  "effect_type": "{action_type}",
  "reason": "一句话解释为什么产生这些后果"
}}

## 硬约束
- **货币守恒**：所有 agent 的 cash_delta 之和必须为 0（交易双方一出一收）
- 不产生凭空的价值或销毁物品
- 后果必须与动作类型和 payload 参数一致
- 如果动作不涉及某个 agent，不要为它生成 delta
- food_security_delta 必须在 [-1, 1] 范围内
- 所有金额必须是正数

## 常见动作的默认值
- trade: 买家 cash_delta = -price, 卖家 cash_delta = +price
- gift: 赠送者无现金变化，受赠者无现金变化（物品转移）
- craft: 制作者无现金变化，产生物品在 inventory_add

返回 JSON，不要有 markdown 代码块标记。
"""


def _build_consequence_prompt(
    action_type: str,
    agent_id: str,
    target_agent_id: str | None,
    target_location_id: str | None,
    raw_intent: str | None,
    payload: dict,
    actor_cash: float,
    actor_employment: str,
    actor_food_security: float,
    target_cash: float | None,
    target_employment: str | None,
    target_food_security: float | None,
    matched_rules: str,
) -> str:
    """Build the consequence generation prompt."""
    return CONSEQUENCE_PROMPT_TEMPLATE.format(
        action_type=action_type,
        agent_id=agent_id,
        target_agent_id=target_agent_id or "无",
        target_location_id=target_location_id or "无",
        raw_intent=raw_intent or "无",
        payload=json.dumps(payload, ensure_ascii=False),
        actor_cash=actor_cash,
        actor_employment=actor_employment,
        actor_food_security=actor_food_security,
        target_cash=target_cash if target_cash is not None else "无",
        target_employment=target_employment or "无",
        target_food_security=target_food_security if target_food_security is not None else "无",
        matched_rules=matched_rules or "无特殊规则",
    )


def _parse_consequence_response(response_text: str) -> StateDelta | None:
    """Parse the LLM response into a StateDelta."""
    from app.agent.prompt_loader import PromptLoader

    try:
        json_data = PromptLoader.extract_json_from_text(response_text)
        if json_data is None:
            logger.warning("consequence_generator: no JSON found in response")
            return None

        # Build agent_deltas
        agent_deltas = {}
        for agent_id, delta_dict in json_data.get("agent_deltas", {}).items():
            agent_deltas[agent_id] = AgentDelta(
                cash_delta=delta_dict.get("cash_delta", 0.0),
                food_security_delta=delta_dict.get("food_security_delta", 0.0),
                inventory_add=delta_dict.get("inventory_add", []),
                inventory_remove=delta_dict.get("inventory_remove", []),
                employment_status=delta_dict.get("employment_status"),
                status_updates=delta_dict.get("status_updates", {}),
            )

        # Build relationship_deltas
        relationship_deltas = {}
        for agent_pair, delta_dict in json_data.get("relationship_deltas", {}).items():
            relationship_deltas[agent_pair] = RelationshipDelta(
                familiarity_delta=delta_dict.get("familiarity_delta", 0.0),
                trust_delta=delta_dict.get("trust_delta", 0.0),
                affinity_delta=delta_dict.get("affinity_delta", 0.0),
            )

        # Build memory_fragments
        memory_fragments = [
            MemoryFragment(agent_id=m.get("agent_id"), content=m.get("content", ""))
            for m in json_data.get("memory_fragments", [])
            if m.get("agent_id") and m.get("content")
        ]

        return StateDelta(
            agent_deltas=agent_deltas,
            world_deltas=WorldDelta(),
            relationship_deltas=relationship_deltas,
            memory_fragments=memory_fragments,
            effect_type=json_data.get("effect_type", "unknown"),
            reason=json_data.get("reason", ""),
        )

    except Exception as exc:
        logger.warning("consequence_generator: failed to parse response: %s", exc)
        return None


async def generate_consequences(
    *,
    action_type: str,
    agent_id: str,
    target_agent_id: str | None,
    target_location_id: str | None,
    raw_intent: str | None,
    payload: dict,
    actor_cash: float,
    actor_employment: str,
    actor_food_security: float,
    target_cash: float | None = None,
    target_employment: str | None = None,
    target_food_security: float | None = None,
    matched_rules: str | None = None,
    max_budget_usd: float = 0.05,
) -> StateDelta | None:
    """Generate consequences for a free action using LLM.

    Args:
        action_type: The type of free action (trade, gift, craft, etc.)
        agent_id: The agent performing the action
        target_agent_id: The target agent (if any)
        target_location_id: The target location (if any)
        raw_intent: The original intent description
        payload: The action parameters
        actor_cash: Actor's current cash
        actor_employment: Actor's employment status
        actor_food_security: Actor's food security level
        target_cash: Target's current cash (if target exists)
        target_employment: Target's employment status (if target exists)
        target_food_security: Target's food security level (if target exists)
        matched_rules: Description of matched rules
        max_budget_usd: Maximum budget for LLM call

    Returns:
        StateDelta if generation succeeded and passes validation, None otherwise
    """
    import shutil

    if shutil.which("claude") is None:
        logger.warning("consequence_generator: claude CLI not available")
        return None

    prompt = _build_consequence_prompt(
        action_type=action_type,
        agent_id=agent_id,
        target_agent_id=target_agent_id,
        target_location_id=target_location_id,
        raw_intent=raw_intent,
        payload=payload,
        actor_cash=actor_cash,
        actor_employment=actor_employment,
        actor_food_security=actor_food_security,
        target_cash=target_cash,
        target_employment=target_employment,
        target_food_security=target_food_security,
        matched_rules=matched_rules,
    )

    try:
        from app.agent.system_prompt import build_system_prompt
        from app.cognition.claude.sdk_options import build_sdk_options
        from app.infra.settings import get_settings

        settings = get_settings()
        options = build_sdk_options(
            settings,
            max_turns=4,
            max_budget_usd=max_budget_usd,
            model=settings.llm_model,
            cwd=str(settings.project_root),
            system_prompt=build_system_prompt(),
        )

        result_text = await run_text_query(prompt=prompt, options=options)

        if not result_text:
            logger.warning("consequence_generator: empty response")
            return None

        state_delta = _parse_consequence_response(result_text)
        if state_delta is None:
            return None

        # Validate currency conservation
        if not state_delta.validate_currency_conservation():
            logger.warning(
                "consequence_generator: currency conservation violated for action_type=%s",
                action_type,
            )
            return None

        return state_delta

    except Exception as exc:
        logger.warning("consequence_generator: LLM call failed: %s", exc)
        return None
