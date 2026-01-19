import uvicorn
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from fastapi import FastAPI, Request
from app.mcp_server.tools import (
    search_books_by_context,
    search_book_specifically,
    get_book_details,
    get_system_status
)

app = FastAPI(title="Aladin Book MCP Server")
mcp_server = Server("AladinBookServer")
sse = SseServerTransport("/messages")


@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        # [통합 검색 도구]
        types.Tool(
            name="search_books",
            description="""
            책을 검색하거나 추천합니다. 
            사용자가 '3만원 이하', 'IT 분야' 처럼 조건을 말하면 filters에 반드시 포함시키세요.
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 주제, 키워드, 또는 질문 내용"
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["context", "keyword"],
                        "description": "context: 주제/상황/추천 요청 시 (RAG), keyword: 정확한 제목/저자 검색 시"
                    },
                    "filters": {
                        "type": "object",
                        "description": "가격, 카테고리 등 제약 조건",
                        "properties": {
                            "max_price": {
                                "type": "integer",
                                "description": "최대 가격 (원 단위). 예: 20000"
                            },
                            "category_name": {
                                "type": "string",
                                "description": "카테고리명 (예: 컴퓨터/모바일, 소설/시/희곡, 경제경영)"
                            }
                        }
                    }
                },
                "required": ["query"]
            },
        ),
        # [상세 조회 도구]
        types.Tool(
            name="get_details",
            description="특정 책의 ISBN을 이용해 상세 정보(재고, 전자책 등)를 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "isbn": {"type": "string"}
                },
                "required": ["isbn"],
            },
        ),
        types.Tool(
            name="status",
            description="시스템 상태 확인",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    if name == "search_books":
        query = arguments.get("query")
        search_type = arguments.get("search_type", "context")
        filters = arguments.get("filters", {})  # 필터 추출

        if search_type == "keyword":
            result = search_book_specifically(query, filters)
        else:
            result = search_books_by_context(query, filters)

        return [types.TextContent(type="text", text=result)]

    elif name == "get_details":
        result = get_book_details(arguments["isbn"])
        return [types.TextContent(type="text", text=result)]

    elif name == "status":
        return [types.TextContent(type="text", text=get_system_status())]

    raise ValueError(f"Unknown tool: {name}")


# (이하 엔드포인트 코드는 기존과 동일)
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp_server.run(streams[0], streams[1], mcp_server.create_initialization_options())


async def handle_messages(request: Request):
    return sse.handle_post_message


app.add_route("/sse", handle_sse, methods=["GET"])
app.add_route("/messages", handle_messages, methods=["POST"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8081)