"""
logic/agent.py — Pure LLM-agent functions for Phase 8.5.

No side effects, no runtime state. All functions are synchronous and can be
tested independently of the simulation loop.

Environment variables consumed (read at call time — never cached at module level):
    LLM_BASE_URL  — base URL of the OpenAI-compatible API  (e.g. https://ai.prv.jerem.ovh/openai)
    LLM_MODEL     — model identifier                       (e.g. Qwen3.6-35B-A3B-MXFP4_MOE)
    LLM_API_KEY   — bearer token
    LLM_MODE      — "json" | "tools"  (default "json")
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from ..models import (
    AgentAction,
    AgentActionType,
    AgentMemory,
    StateData,
    StateType,
)

logger = logging.getLogger(__name__)

# ── Tool schema ───────────────────────────────────────────────────────────────

AGENT_TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "NoOp",
            "description": "Take no action this tick. Use when the situation is stable.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ProposeContract",
            "description": "Propose a resource-delivery or territorial contract to a corporation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "targetCorpId": {"type": "string", "description": "ID of the corporation to address"},
                    "resourceType": {"type": "string", "description": "Resource to request (e.g. 'Iron', 'Energy')"},
                    "quantity": {"type": "number", "description": "Required quantity per tick"},
                    "durationTicks": {"type": "integer", "description": "Contract duration in ticks"},
                    "rewardCredits": {"type": "number", "description": "Credits offered to the corporation"},
                },
                "required": ["targetCorpId", "resourceType", "quantity", "durationTicks", "rewardCredits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "SetTolerance",
            "description": "Adjust the tolerance threshold — the economic dominance above which nationalization is triggered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "newThreshold": {
                        "type": "number",
                        "description": "New tolerance value [0.0–1.0]. Lower = stricter.",
                    },
                },
                "required": ["newThreshold"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "TriggerNationalization",
            "description": "Start a nationalization process against a corporation that exceeded tolerance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "targetCorpId": {"type": "string", "description": "Corporation to nationalize"},
                    "tileId": {"type": "string", "description": "Tile (building) to reclaim"},
                },
                "required": ["targetCorpId", "tileId"],
            },
        },
    },
]

# ── Prompt helpers ────────────────────────────────────────────────────────────

_PERSONALITY: dict[StateType, str] = {
    StateType.Capitalist: (
        "You are a pragmatic capitalist state. You prioritize economic growth and stability. "
        "You tolerate corporate presence as long as it benefits your population. "
        "You raise tolerance thresholds before resorting to nationalization."
    ),
    StateType.Nationalist: (
        "You are a nationalist state. You are protective of your territory and wary of "
        "corporate dominance. You have a lower threshold for nationalization and prefer "
        "local control of key resources."
    ),
}

_RULES = (
    "\n\nIMPORTANT RULES:\n"
    "1. You must act in the INTERESTS of your state and its population, not any individual corporation.\n"
    "2. You must be IMPARTIAL — do not favour a corporation because it previously helped you.\n"
    "3. RESPECT your state's agenda: use SetTolerance cautiously, TriggerNationalization only when justified.\n"
    "4. Choose NoOp when no significant change is needed. Do not over-react to minor fluctuations.\n"
    "5. Return EXACTLY ONE action. Do not explain your choice outside the action schema.\n"
)


def build_system_prompt(state: StateData) -> str:
    """Return a system prompt tailored to the state's type."""
    personality = _PERSONALITY.get(state.stateType, _PERSONALITY[StateType.Capitalist])
    return personality + _RULES


def build_state_context(
    state: StateData,
    tick: int,
    scoreboard: list[dict] | None = None,
    recent_events: list[dict] | None = None,
    memory: AgentMemory | None = None,
    reputations: dict[str, float] | None = None,
) -> str:
    """
    Assemble a compact JSON context string for the LLM prompt.

    All args beyond `state` are optional enrichment layers that runtime.py
    may provide. Missing layers are omitted from the context object.
    """
    ctx: dict[str, Any] = {
        "tick": tick,
        "state": {
            "id": state.id,
            "name": state.name,
            "type": state.stateType.name,
            "tileCount": len(state.tileIds),
            "bureaucracy": state.bureaucracy,
            "corruptionRate": state.corruptionRate,
            "toleranceThreshold": state.toleranceThreshold,
        },
    }
    if scoreboard:
        ctx["scoreboard"] = scoreboard
    if recent_events:
        ctx["recentEvents"] = recent_events
    if reputations:
        ctx["reputations"] = reputations
    if memory:
        ctx["memory"] = {
            "recentDecisions": memory.recentDecisions[-5:],
            "relationshipNotes": memory.relationshipNotes,
            "lastTickActed": memory.lastTickActed,
        }
    return json.dumps(ctx, ensure_ascii=False)


# ── LLM call helpers ──────────────────────────────────────────────────────────

def _llm_headers(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def call_llm_json(
    messages: list[dict],
    llm_url: str,
    model: str,
    api_key: str,
    timeout: float = 60.0,
) -> dict:
    """
    POST to /chat/completions with response_format={"type":"json_object"}.

    Returns the parsed JSON dict from the first message content.
    Raises httpx.HTTPStatusError or ValueError on failure.
    """
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
    }
    resp = httpx.post(
        f"{llm_url}/chat/completions",
        json=payload,
        headers=_llm_headers(api_key),
        timeout=timeout,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


def call_llm_tools(
    messages: list[dict],
    tools: list[dict],
    llm_url: str,
    model: str,
    api_key: str,
    timeout: float = 60.0,
) -> dict:
    """
    POST to /chat/completions with tool_choice="required".

    Returns {"name": ..., "arguments": {...}} for the first tool call.
    Raises httpx.HTTPStatusError or ValueError on failure.
    """
    payload = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "required",
        "temperature": 0.3,
    }
    resp = httpx.post(
        f"{llm_url}/chat/completions",
        json=payload,
        headers=_llm_headers(api_key),
        timeout=timeout,
    )
    resp.raise_for_status()
    tool_call = resp.json()["choices"][0]["message"]["tool_calls"][0]
    return {
        "name": tool_call["function"]["name"],
        "arguments": json.loads(tool_call["function"]["arguments"]),
    }


# ── Action parsing ────────────────────────────────────────────────────────────

_ACTION_TYPE_MAP: dict[str, AgentActionType] = {
    "NoOp": AgentActionType.NoOp,
    "ProposeContract": AgentActionType.ProposeContract,
    "SetTolerance": AgentActionType.SetTolerance,
    "TriggerNationalization": AgentActionType.TriggerNationalization,
}


def parse_action_from_json(raw: dict, entity_id: str) -> AgentAction:
    """
    Parse a raw dict (from JSON-mode response) into an AgentAction.

    Expected schema:
        {"action": "NoOp"|..., "params": {...}, "reasoning": "..."}
    Falls back to NoOp on any parsing error.
    """
    try:
        action_name = raw.get("action", "NoOp")
        action_type = _ACTION_TYPE_MAP.get(action_name, AgentActionType.NoOp)
        return AgentAction(
            entityId=entity_id,
            actionType=action_type,
            params=raw.get("params", {}),
            reasoning=raw.get("reasoning", ""),
        )
    except Exception as exc:
        logger.warning("parse_action_from_json failed for %s: %s", entity_id, exc)
        return AgentAction(entityId=entity_id)


def parse_action_from_tool_call(tool_call: dict, entity_id: str) -> AgentAction:
    """
    Parse a tool-call dict {"name": ..., "arguments": {...}} into an AgentAction.

    Falls back to NoOp on any parsing error.
    """
    try:
        action_type = _ACTION_TYPE_MAP.get(tool_call.get("name", "NoOp"), AgentActionType.NoOp)
        return AgentAction(
            entityId=entity_id,
            actionType=action_type,
            params=tool_call.get("arguments", {}),
            reasoning="",
        )
    except Exception as exc:
        logger.warning("parse_action_from_tool_call failed for %s: %s", entity_id, exc)
        return AgentAction(entityId=entity_id)


# ── High-level entry point ────────────────────────────────────────────────────

def run_agent(
    state: StateData,
    tick: int,
    memory: AgentMemory | None = None,
    scoreboard: list[dict] | None = None,
    recent_events: list[dict] | None = None,
    reputations: dict[str, float] | None = None,
) -> AgentAction:
    """
    Run one agent decision cycle for a given state.

    Reads LLM_BASE_URL / LLM_MODEL / LLM_API_KEY / LLM_MODE from env.
    Returns a fallback NoOp AgentAction on any connectivity or parsing error.
    """
    llm_url  = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    model    = os.environ.get("LLM_MODEL", "")
    api_key  = os.environ.get("LLM_API_KEY", "")
    llm_mode = os.environ.get("LLM_MODE", "json").lower()

    if not llm_url or not model or not api_key:
        logger.warning("run_agent: LLM env vars missing — returning NoOp for state %s", state.id)
        return AgentAction(entityId=state.id)

    system_msg = build_system_prompt(state)
    context    = build_state_context(
        state, tick,
        scoreboard=scoreboard,
        recent_events=recent_events,
        memory=memory,
        reputations=reputations,
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": context},
    ]

    try:
        if llm_mode == "tools":
            raw = call_llm_tools(messages, AGENT_TOOLS_SCHEMA, llm_url, model, api_key)
            return parse_action_from_tool_call(raw, state.id)
        else:
            raw = call_llm_json(messages, llm_url, model, api_key)
            return parse_action_from_json(raw, state.id)
    except Exception as exc:
        logger.error("run_agent LLM call failed for state %s: %s", state.id, exc)
        return AgentAction(entityId=state.id)
