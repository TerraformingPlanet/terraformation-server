from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx


def _extract_sse_json(body: str) -> dict:
    for line in body.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    raise RuntimeError("No SSE data payload found in MCP response")


def _call_tool(client: httpx.Client, base_url: str, headers: dict[str, str], tool_name: str, arguments: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 2 if tool_name == "run_generation_quality_suite" else 3,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    response = client.post(base_url, headers=headers, json=payload)
    response.raise_for_status()
    return _extract_sse_json(response.text)


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe FastMCP streamable-http endpoint")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/mcp")
    parser.add_argument("--output", default="Artifacts/mcp-http-probe.json")
    args = parser.parse_args()

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "github-actions-probe", "version": "1.0"},
        },
    }
    with httpx.Client(timeout=60) as client:
        initialize_response = client.post(args.base_url, headers=headers, json=initialize_payload)
        initialize_response.raise_for_status()
        session_id = initialize_response.headers.get("mcp-session-id")
        if not session_id:
            raise RuntimeError("Missing mcp-session-id header on initialize response")

        tool_headers = dict(headers)
        tool_headers["mcp-session-id"] = session_id
        quality_call = _call_tool(
            client, args.base_url, tool_headers,
            "run_generation_quality_suite", {"h3_resolution": 2}
        )
        compare_call = _call_tool(
            client, args.base_url, tool_headers,
            "compare_generation_profiles", {"profile_a": "Coast", "profile_b": "Ocean", "h3_resolution": 2}
        )

    init_payload = _extract_sse_json(initialize_response.text)
    quality_structured = (((quality_call.get("result") or {}).get("structuredContent")) or {})
    compare_structured = (((compare_call.get("result") or {}).get("structuredContent")) or {})
    compare_delta = compare_structured.get("delta") or []
    passed = bool(quality_structured.get("passed")) and len(compare_delta) > 0

    output_payload = {
        "baseUrl": args.base_url,
        "sessionId": session_id,
        "initialize": init_payload,
        "qualityToolCall": quality_call,
        "qualityStructuredContent": quality_structured,
        "compareToolCall": compare_call,
        "compareStructuredContent": compare_structured,
        "ok": passed,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")

    print(json.dumps({
        "ok": passed,
        "sessionId": session_id,
        "server": ((init_payload.get("result") or {}).get("serverInfo") or {}).get("name"),
        "tools": ["run_generation_quality_suite", "compare_generation_profiles"],
    }, indent=2))

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())