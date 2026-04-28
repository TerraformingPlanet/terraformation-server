"""
logic/agent.py — Pure LLM-agent functions for Phase 8.5 (States) + Phase 11.2 M2 (Corporations).

No side effects, no runtime state. All functions are synchronous and can be
tested independently of the simulation loop.

Environment variables consumed (read at call time — never cached at module level):
    LLM_BASE_URL    — base URL of the OpenAI-compatible API  (e.g. https://ai.prv.jerem.ovh/openai)
    LLM_MODEL       — default model identifier
    LLM_MODEL_FAST  — model used for urgent decisions (tick-critical); fallback → LLM_MODEL
    LLM_MODEL_DEEP  — model used for non-urgent decisions (strategic planning); fallback → LLM_MODEL
    LLM_API_KEY     — bearer token
    LLM_MODE        — "json" | "tools"  (default "json")
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
    CorpProfile,
    CorporationData,
    StateData,
    StateType,
)
from .corp_fsm import CorpSimSnapshot

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
    "5. CRITICAL: if the context contains \"inCrisis\": true, you MUST choose ProposeContract or SetTolerance.\n"
    "   NoOp is FORBIDDEN when inCrisis=true. Passive maintenance is not an acceptable action during a crisis.\n"
    "6. Return EXACTLY ONE action using the JSON schema below. Do not add extra keys.\n"
    "\nOUTPUT SCHEMA (strict — no other keys allowed):\n"
    '{"action": "<NoOp|SetTolerance|ProposeContract|TriggerNationalization>",\n'
    ' "params": {<see below>},\n'
    ' "reasoning": "<one sentence>"}\n'
    "\nPARAMS per action:\n"
    "  NoOp                  : {}\n"
    '  SetTolerance          : {"newThreshold": <float 0.0-1.0>}\n'
    '  ProposeContract       : {"targetCorpId": "...", "resourceType": "...",\n'
    '                           "quantity": <number>, "durationTicks": <int>, "rewardCredits": <number>}\n'
    '  TriggerNationalization: {"targetCorpId": "...", "tileId": "..."}\n'
)

_RULES_TOOLS = (
    "\n\nIMPORTANT RULES:\n"
    "1. You must act in the INTERESTS of your state and its population, not any individual corporation.\n"
    "2. You must be IMPARTIAL — do not favour a corporation because it previously helped you.\n"
    "3. RESPECT your state's agenda: use SetTolerance cautiously, TriggerNationalization only when justified.\n"
    "4. Choose NoOp when no significant change is needed. Do not over-react to minor fluctuations.\n"
    "5. CRITICAL: if the context contains \"inCrisis\": true, you MUST choose ProposeContract or SetTolerance.\n"
    "   NoOp is FORBIDDEN when inCrisis=true. Passive maintenance is not an acceptable action during a crisis.\n"
    "6. Call EXACTLY ONE of the available tools to return your decision. Do NOT return JSON text.\n"
)


def build_system_prompt(state: StateData, mode: str = "json") -> str:
    """Return a system prompt tailored to the state's type and LLM mode."""
    personality = _PERSONALITY.get(state.stateType, _PERSONALITY[StateType.Capitalist])
    rules = _RULES_TOOLS if mode == "tools" else _RULES
    return personality + rules


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

    Automatically computes corp_dominanceRatio and thresholdBreached so the
    LLM always receives an explicit pressure signal rather than raw tile counts.
    """
    tile_count = len(state.tileIds)
    ctx: dict[str, Any] = {
        "tick": tick,
        "state": {
            "id": state.id,
            "name": state.name,
            "type": state.stateType.name,
            "tileCount": tile_count,
            "bureaucracy": state.bureaucracy,
            "corruptionRate": state.corruptionRate,
            "toleranceThreshold": state.toleranceThreshold,
        },
    }

    # Crisis flag: explicit signal for the LLM
    in_crisis = state.bureaucracy > 0.4 or state.corruptionRate > 0.4
    if in_crisis:
        ctx["state"]["inCrisis"] = True
        ctx["state"]["crisisAlert"] = (
            f"CRISIS: bureaucracy={state.bureaucracy:.0%}, "
            f"corruption={state.corruptionRate:.0%}. "
            "You MUST take action (ProposeContract or SetTolerance). NoOp is not acceptable."
        )

    # Compute derived pressure signals from scoreboard
    if scoreboard:
        ctx["scoreboard"] = scoreboard
        if tile_count > 0:
            top = max(scoreboard, key=lambda e: e.get("totalTiles", 0), default=None)
            if top:
                dominance = round(top.get("totalTiles", 0) / tile_count, 3)
                breached = dominance > state.toleranceThreshold
                ctx["state"]["topCorpId"] = top.get("corpId", "")
                ctx["state"]["topCorpDominanceRatio"] = dominance
                ctx["state"]["toleranceBreached"] = breached
                if breached:
                    ctx["state"]["alert"] = (
                        f"ALERT: {top.get('corpId','')} controls {dominance:.0%} of your territory "
                        f"(tolerance limit: {state.toleranceThreshold:.0%}). Action is required."
                    )

    if recent_events:
        ctx["recentEvents"] = recent_events
        broken = [e for e in recent_events if e.get("type") == "ContractBroken"]
        if broken:
            offenders = list({e.get("corpId", "unknown") for e in broken})
            ctx["state"]["brokenContractAlert"] = (
                f"ALERT: {len(broken)} contract(s) recently broken by {', '.join(offenders)}. "
                "SetTolerance or TriggerNationalization recommended."
            )
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
    timeout: float = 180.0,
    temperature: float = 0.3,
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
        "temperature": temperature,
        "max_tokens": 400,
        "chat_template_kwargs": {"enable_thinking": False},
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
    timeout: float = 180.0,
    temperature: float = 0.3,
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
        "temperature": temperature,
        "max_tokens": 300,  # un tool call ne dépasse jamais quelques tokens
        "chat_template_kwargs": {"enable_thinking": False},
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


# ── Corpo tool schema (Phase 11.2 M2) ────────────────────────────────────────

CORP_AGENT_TOOLS_SCHEMA: list[dict] = [
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
            "name": "UpdateFsmThresholds",
            "description": (
                "Override one or more FSM decision thresholds. "
                "Use to make the corporation more aggressive or conservative."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "thresholds": {
                        "type": "object",
                        "description": (
                            "Dict of threshold key → float value. "
                            "Keys: expand_min_credits, expand_max_tiles, "
                            "build_bottleneck_threshold, trade_price_margin, "
                            "raid_force_ratio, idle_min_credits."
                        ),
                        "additionalProperties": {"type": "number"},
                    },
                },
                "required": ["thresholds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ReorderConstructionQueue",
            "description": "Change the priority of a building in the construction queue for a territory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "territoryId": {"type": "string", "description": "Territory whose queue to reorder"},
                    "newOrder": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of building type names (most urgent first)",
                    },
                },
                "required": ["territoryId", "newOrder"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ProposeContract",
            "description": "Propose a resource-delivery contract to another corporation or a state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "targetCorpId": {"type": "string", "description": "ID of the target entity"},
                    "resourceType": {"type": "string", "description": "Resource to deliver (e.g. 'Iron', 'Energy')"},
                    "quantity": {"type": "number", "description": "Required quantity per tick"},
                    "durationTicks": {"type": "integer", "description": "Contract duration in ticks"},
                    "rewardCredits": {"type": "number", "description": "Credits offered to the corporation"},
                },
                "required": ["targetCorpId", "resourceType", "quantity", "durationTicks", "rewardCredits"],
            },
        },
    },
]

# ── Action parsing ────────────────────────────────────────────────────────────

_ACTION_TYPE_MAP: dict[str, AgentActionType] = {
    "NoOp": AgentActionType.NoOp,
    "ProposeContract": AgentActionType.ProposeContract,
    "SetTolerance": AgentActionType.SetTolerance,
    "TriggerNationalization": AgentActionType.TriggerNationalization,
    # Phase 11.2 — Corporation actions
    "ClaimTile": AgentActionType.ClaimTile,
    "ConstructBuilding": AgentActionType.ConstructBuilding,
    "UpdateFsmThresholds": AgentActionType.UpdateFsmThresholds,
    "ReorderConstructionQueue": AgentActionType.ReorderConstructionQueue,
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

def _resolve_model(urgency: bool) -> str:
    """
    Select the appropriate model based on urgency.

    urgency=True  → LLM_MODEL_FAST (low-latency, tick-critical decisions)
    urgency=False → LLM_MODEL_DEEP (higher quality, strategic/planning decisions)
    Both fall back to LLM_MODEL when not set.
    """
    default = os.environ.get("LLM_MODEL", "")
    if urgency:
        return os.environ.get("LLM_MODEL_FAST") or default
    return os.environ.get("LLM_MODEL_DEEP") or default


def run_agent(
    state: StateData,
    tick: int,
    memory: AgentMemory | None = None,
    scoreboard: list[dict] | None = None,
    recent_events: list[dict] | None = None,
    reputations: dict[str, float] | None = None,
    urgency: bool = False,
) -> AgentAction:
    """
    Run one agent decision cycle for a given state.

    Reads LLM_BASE_URL / LLM_API_KEY / LLM_MODE from env.
    Model is selected via _resolve_model(urgency):
      urgency=True  → LLM_MODEL_FAST (fast reaction, e.g. nationalization trigger)
      urgency=False → LLM_MODEL_DEEP (strategic reasoning, e.g. long-term contract)
    Returns a fallback NoOp AgentAction on any connectivity or parsing error.
    """
    llm_url  = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    model    = _resolve_model(urgency)
    api_key  = os.environ.get("LLM_API_KEY", "")
    llm_mode = os.environ.get("LLM_MODE", "json").lower()

    if not llm_url or not model or not api_key:
        logger.warning("run_agent: LLM env vars missing (urgency=%s) — returning NoOp for state %s", urgency, state.id)
        return AgentAction(entityId=state.id)

    system_msg = build_system_prompt(state, mode=llm_mode)
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


# ── Corpo agent helpers (Phase 11.2 M2) ──────────────────────────────────────

_CORP_PERSONALITY: dict[CorpProfile, str] = {
    CorpProfile.Economiste: (
        "You are an economically-driven AI corporation. Your priority is production efficiency, "
        "market arbitrage, and maximising credits per tick. You invest in buildings before "
        "claiming new tiles. You prefer trade contracts over direct conflict."
    ),
    CorpProfile.Expansionniste: (
        "You are an expansion-focused AI corporation. Your priority is territory: claim tiles "
        "aggressively, establish a wide resource base, and outgrow rivals. You spend credits on "
        "territory before buildings unless you are resource-starved."
    ),
    CorpProfile.Militariste: (
        "You are a militarist AI corporation. Your priority is dominance: weaken rivals by "
        "raiding adjacent tiles, control strategic chokepoints, and force competitors into "
        "expensive negotiations. You adjust FSM thresholds to stay in Raiding mode longer."
    ),
}

_CORP_RULES = (
    "\n\nIMPORTANT RULES:\n"
    "1. Act in the STRATEGIC INTEREST of your corporation — maximise score and survival.\n"
    "2. Stay in character: your profile defines how you prioritise actions.\n"
    "3. UpdateFsmThresholds if market or geopolitical conditions have shifted significantly.\n"
    "4. ReorderConstructionQueue only when production priorities have genuinely changed.\n"
    "5. Choose NoOp when the FSM is already handling the situation correctly.\n"
    "6. Return EXACTLY ONE action using the JSON schema below. Do not add extra keys.\n"
    "\nOUTPUT SCHEMA (strict — no other keys allowed):\n"
    '{"action": "<NoOp|UpdateFsmThresholds|ReorderConstructionQueue|ProposeContract>",\n'
    ' "params": {<see below>},\n'
    ' "reasoning": "<one sentence>"}\n'
    "\nPARAMS per action:\n"
    "  NoOp                    : {}\n"
    '  UpdateFsmThresholds     : {"thresholds": {"<key>": <float>, ...}}\n'
    '    keys: expand_min_credits, expand_max_tiles, build_bottleneck_threshold,\n'
    '          trade_price_margin, raid_force_ratio, idle_min_credits\n'
    '  ReorderConstructionQueue: {"territoryId": "...", "newOrder": ["BuildingType", ...]}\n'
    '  ProposeContract         : {"targetCorpId": "...", "resourceType": "...",\n'
    '                             "quantity": <number>, "durationTicks": <int>, "rewardCredits": <number>}\n'
)


def build_corp_system_prompt(corp: CorporationData) -> str:
    """Return a system prompt tailored to the corporation's profile."""
    personality = _CORP_PERSONALITY.get(corp.profile, _CORP_PERSONALITY[CorpProfile.Economiste])
    return personality + _CORP_RULES


def build_corp_context(
    corp: CorporationData,
    tick: int,
    snapshot: CorpSimSnapshot,
    memory: AgentMemory | None = None,
    scoreboard: list[dict] | None = None,
    recent_events: list[dict] | None = None,
) -> str:
    """
    Assemble a compact JSON context string for the corporation LLM prompt.

    snapshot provides the current environment view (built lock-free in runtime).
    """
    ctx: dict[str, Any] = {
        "tick": tick,
        "corp": {
            "id": corp.id,
            "name": corp.name,
            "profile": corp.profile.name,
            "fsmState": corp.fsmState.name,
            "credits": corp.credits,
            "tileCount": len(corp.claimedTiles),
            "globalReputation": corp.globalReputation,
            "fsmThresholds": corp.fsmThresholds,
        },
        "environment": {
            "freeTilesAdjacent": len(snapshot.free_tile_ids_adj),
            "resourceStocks": snapshot.resource_stocks,
            "marketPrices": snapshot.market_prices,
            "rivals": [
                {"corpId": cid, "adjTiles": cnt}
                for cid, cnt in snapshot.rival_tile_counts.items()
            ],
            "productionBottleneck": snapshot.production_bottleneck,
            "hasActiveConstruction": snapshot.has_active_construction,
        },
    }
    if scoreboard:
        ctx["scoreboard"] = scoreboard
    if recent_events:
        ctx["recentEvents"] = recent_events
    if memory:
        ctx["memory"] = {
            "recentDecisions": memory.recentDecisions[-5:],
            "lastTickActed": memory.lastTickActed,
        }
    return json.dumps(ctx, ensure_ascii=False)


def run_corp_agent(
    corp: CorporationData,
    tick: int,
    snapshot: CorpSimSnapshot,
    memory: AgentMemory | None = None,
    scoreboard: list[dict] | None = None,
    recent_events: list[dict] | None = None,
    urgency: bool = False,
) -> AgentAction:
    """
    Run one LLM decision cycle for an AI corporation.

    Reads LLM_BASE_URL / LLM_API_KEY / LLM_MODE from env.
    Model is selected via _resolve_model(urgency):
      urgency=True  → LLM_MODEL_FAST (e.g. raid reaction, tile contest)
      urgency=False → LLM_MODEL_DEEP (e.g. queue reorder, FSM threshold tuning)
    Returns a fallback NoOp AgentAction on any connectivity or parsing error.
    """
    llm_url  = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    model    = _resolve_model(urgency)
    api_key  = os.environ.get("LLM_API_KEY", "")
    llm_mode = os.environ.get("LLM_MODE", "json").lower()

    if not llm_url or not model or not api_key:
        logger.warning("run_corp_agent: LLM env vars missing (urgency=%s) — returning NoOp for corp %s", urgency, corp.id)
        return AgentAction(entityId=corp.id)

    system_msg = build_corp_system_prompt(corp)
    context    = build_corp_context(
        corp, tick, snapshot,
        memory=memory,
        scoreboard=scoreboard,
        recent_events=recent_events,
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": context},
    ]

    try:
        if llm_mode == "tools":
            raw = call_llm_tools(messages, CORP_AGENT_TOOLS_SCHEMA, llm_url, model, api_key)
            return parse_action_from_tool_call(raw, corp.id)
        else:
            raw = call_llm_json(messages, llm_url, model, api_key)
            return parse_action_from_json(raw, corp.id)
    except Exception as exc:
        logger.error("run_corp_agent LLM call failed for corp %s: %s", corp.id, exc)
        return AgentAction(entityId=corp.id)
