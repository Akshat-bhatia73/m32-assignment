"""Vercel AI SDK v5 UI Message Stream protocol helpers.

The frontend uses `@ai-sdk/react` `useChat` with a default (SSE) transport. Each event is
emitted as an SSE `data: <json>` line; the stream terminates with `[DONE]`. Responses must
carry the `x-vercel-ai-ui-message-stream: v1` header (see `stream_headers`).

Reference part types we use:
  - start / finish            — message envelope
  - text-start/-delta/-end    — streamed assistant text (grouped by a shared id)
  - data-<name>               — custom typed data parts (e.g. data-action-item) for the board
  - tool-input-available /
    tool-output-available     — visible tool calls (extract / schedule / send)
"""

import json
from typing import Any

STREAM_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "x-vercel-ai-ui-message-stream": "v1",
    "x-accel-buffering": "no",  # disable proxy buffering (nginx/Render)
}


def sse(part: dict[str, Any]) -> str:
    """Serialize one protocol part as an SSE data line."""
    return f"data: {json.dumps(part, separators=(',', ':'))}\n\n"


def done() -> str:
    return "data: [DONE]\n\n"


# --- part builders ---------------------------------------------------------

def start(message_id: str | None = None) -> dict[str, Any]:
    part: dict[str, Any] = {"type": "start"}
    if message_id:
        part["messageId"] = message_id
    return part


def text_start(text_id: str) -> dict[str, Any]:
    return {"type": "text-start", "id": text_id}


def text_delta(text_id: str, delta: str) -> dict[str, Any]:
    return {"type": "text-delta", "id": text_id, "delta": delta}


def text_end(text_id: str) -> dict[str, Any]:
    return {"type": "text-end", "id": text_id}


def data_part(name: str, data: dict[str, Any], part_id: str | None = None) -> dict[str, Any]:
    """A custom data-<name> part. `part_id` lets the client reconcile updates in place."""
    part: dict[str, Any] = {"type": f"data-{name}", "data": data}
    if part_id:
        part["id"] = part_id
    return part


def tool_input(tool_call_id: str, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "tool-input-available",
        "toolCallId": tool_call_id,
        "toolName": tool_name,
        "input": args,
    }


def tool_output(tool_call_id: str, output: Any) -> dict[str, Any]:
    return {"type": "tool-output-available", "toolCallId": tool_call_id, "output": output}


def finish() -> dict[str, Any]:
    return {"type": "finish"}


def error(message: str) -> dict[str, Any]:
    return {"type": "error", "errorText": message}
