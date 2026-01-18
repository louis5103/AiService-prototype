import uvicorn
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request

# 도구 로직 임포트
from app.mcp_server.tools import calculate_sum, get_system_status

# 1. MCP Server 인스턴스 생성 (Low-level)
mcp_server = Server("RemoteMathServer")


# 2. 도구 목록 정의 (List Tools Handler)
# 클라이언트(Agent)가 "어떤 도구가 있어?"라고 물어볼 때 응답하는 함수입니다.
@mcp_server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="add",
            description="두 숫자를 더합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {"type": "integer", "description": "첫 번째 숫자"},
                    "b": {"type": "integer", "description": "두 번째 숫자"},
                },
                "required": ["a", "b"],
            },
        ),
        types.Tool(
            name="status",
            description="시스템 상태를 확인합니다.",
            inputSchema={
                "type": "object",
                "properties": {},  # 입력 인자 없음
            },
        ),
    ]


# 3. 도구 실행 핸들러 (Call Tool Handler)
# 클라이언트(Agent)가 "이 도구 실행해줘"라고 요청할 때 처리하는 함수입니다.
@mcp_server.call_tool()
async def handle_call_tool(
        name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "add":
        if not arguments:
            raise ValueError("Arguments required for add")
        # tools.py의 함수 호출
        result = calculate_sum(arguments["a"], arguments["b"])
        return [types.TextContent(type="text", text=str(result))]

    elif name == "status":
        # tools.py의 함수 호출
        result = get_system_status()
        return [types.TextContent(type="text", text=result)]

    raise ValueError(f"Unknown tool: {name}")


# 4. SSE 전송 계층 설정 (기존과 동일)
sse = SseServerTransport("/messages")


async def handle_sse(request: Request):
    async with sse.connect_sse(
            request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0], streams[1], mcp_server.create_initialization_options()
        )


async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)


# 5. 웹 서버 라우팅
routes = [
    Route("/sse", endpoint=handle_sse),
    Route("/messages", endpoint=handle_messages, methods=["POST"]),
]

app = Starlette(routes=routes)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
