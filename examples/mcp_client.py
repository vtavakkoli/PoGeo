"""Minimal PoGeo Streamable HTTP MCP client.

Run the stack, install the project dependencies, then execute:
    python examples/mcp_client.py
"""

from __future__ import annotations

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    async with streamable_http_client("http://localhost:8000/mcp") as streams:
        read_stream, write_stream, _ = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Tools:", [tool.name for tool in tools.tools])

            result = await session.call_tool(
                "find_nearest",
                arguments={
                    "collection_id": "places",
                    "longitude": 16.3731,
                    "latitude": 48.2085,
                    "limit": 3,
                },
            )
            print(result.structuredContent or result.content)


if __name__ == "__main__":
    asyncio.run(main())
