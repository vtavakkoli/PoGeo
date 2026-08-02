from __future__ import annotations

import json
from typing import Any

import httpx

from pogeo.models import ChatRequest, ChatResponse, ToolExecution
from pogeo.runtime import Runtime
from pogeo.tools import TOOL_SCHEMAS, ToolRegistry

SYSTEM_PROMPT = """You are PoGeo, a careful geospatial assistant connected to PostGIS.
Use the supplied tools for every question that depends on map or database content.
Never invent collections, columns, counts, coordinates, or query results.
Never generate or request raw SQL. Start with list_collections when the schema is unclear.
Use WGS84 longitude/latitude coordinates. Keep answers concise and mention the number of results.
The tool layer validates all requests and enforces collection and property allowlists.
"""


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaAgent:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.registry = ToolRegistry(runtime)
        self._client = httpx.AsyncClient(
            base_url=runtime.settings.ollama_base_url.rstrip("/"),
            timeout=runtime.settings.ollama_timeout_seconds,
            limits=httpx.Limits(
                max_connections=32,
                max_keepalive_connections=16,
                keepalive_expiry=30,
            ),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def status(self) -> dict[str, Any]:
        try:
            response = await self._client.get("/api/tags")
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return {
                "available": False,
                "baseUrl": self.runtime.settings.ollama_base_url,
                "model": self.runtime.settings.ollama_model,
                "error": str(exc),
            }
        models = [item.get("name") for item in response.json().get("models", [])]
        return {
            "available": True,
            "baseUrl": self.runtime.settings.ollama_base_url,
            "model": self.runtime.settings.ollama_model,
            "installed": self.runtime.settings.ollama_model in models,
            "models": models,
        }

    async def chat(self, request: ChatRequest) -> ChatResponse:
        messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(message.model_dump() for message in request.history[-20:])

        context = ""
        if request.map_context is not None:
            context = "\nCurrent map context: " + request.map_context.model_dump_json(
                exclude_none=True
            )
        messages.append({"role": "user", "content": request.message + context})

        executions: list[ToolExecution] = []
        last_features: dict[str, Any] | None = None

        for _ in range(self.runtime.settings.max_tool_iterations):
            response = await self._request(messages)
            assistant_message = response.get("message", {})
            tool_calls = assistant_message.get("tool_calls") or []

            if not tool_calls:
                answer = str(assistant_message.get("content") or "No answer was generated.")
                return ChatResponse(
                    answer=answer,
                    model=self.runtime.settings.ollama_model,
                    tool_executions=executions,
                    feature_collection=last_features,
                )

            messages.append(assistant_message)
            for call in tool_calls:
                function = call.get("function", {})
                name = str(function.get("name", ""))
                arguments = function.get("arguments") or {}
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                if not isinstance(arguments, dict):
                    raise ValueError(f"Tool arguments for {name!r} must be an object")

                result = await self.registry.execute(name, arguments)
                executions.append(
                    ToolExecution(name=name, arguments=arguments, summary=result.summary)
                )
                if result.feature_collection is not None:
                    last_features = result.feature_collection
                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(result.content, ensure_ascii=False, default=str),
                    }
                )

        return ChatResponse(
            answer=(
                "The spatial analysis reached the configured tool-iteration limit. "
                "Please make the question more specific."
            ),
            model=self.runtime.settings.ollama_model,
            tool_executions=executions,
            feature_collection=last_features,
        )

    async def _request(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.runtime.settings.ollama_model,
                    "messages": messages,
                    "tools": TOOL_SCHEMAS,
                    "stream": False,
                    "think": False,
                    "options": {"temperature": 0.1},
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(
                "Ollama is unavailable or the configured model is not ready"
            ) from exc
