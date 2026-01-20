import uvicorn
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from fastapi import FastAPI, Request
from app.mcp_server.tools import (
    search_books_by_context, search_book_specifically,
    get_book_details, get_system_status
)

app = FastAPI(title="Aladin Book MCP Server")
mcp_server = Server("AladinBookServer")
sse = SseServerTransport("/messages")

@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="search_books",
            description="책을 검색/추천합니다. 사용자 조건(가격, 평점 등)을 filters에 넣으세요.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "search_type": {"type": "string", "enum": ["context", "keyword"]},
                    "filters": {
                        "type": "object",
                        "properties": {
                            "max_price": {"type": "integer"},
                            "category_name": {"type": "string"},
                            "min_rating": {"type": "number", "description": "최소 평점 (0~10)"},
                            "min_pub_date": {"type": "string", "description": "YYYY-MM-DD 이후 출간"}
                        }
                    }
                },
                "required": ["query"]
            },
        ),
        types.Tool(
            name="get_details",
            description="ISBN으로 상세 정보 조회",
            inputSchema={"type": "object", "properties": {"isbn": {"type": "string"}}, "required": ["isbn"]},
        ),
        types.Tool(name="status", description="상태 확인", inputSchema={"type": "object", "properties": {}})
    ]

@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "search_books":
        q = arguments.get("query")
        stype = arguments.get("search_type", "context")
        filters = arguments.get("filters", {})
        res = search_book_specifically(q, filters) if stype == "keyword" else search_books_by_context(q, filters)
        return [types.TextContent(type="text", text=res)]
    elif name == "get_details":
        return [types.TextContent(type="text", text=get_book_details(arguments["isbn"]))]
    elif name == "status":
        return [types.TextContent(type="text", text=get_system_status())]
    raise ValueError(f"Unknown tool: {name}")

# SSE Endpoints
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())

async def handle_messages(request: Request):
    return sse.handle_post_message

app.add_route("/sse", handle_sse, methods=["GET"])
app.add_route("/messages", handle_messages, methods=["POST"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)