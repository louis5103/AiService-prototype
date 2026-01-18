import uvicorn
import mcp.types as types
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from fastapi import FastAPI, Request

# 도구 로직 임포트
from app.mcp_server.tools import calculate_sum, get_system_status

# 1. FastAPI 앱 초기화
app = FastAPI(title="Remote Math MCP Server")

# 2. MCP Server 인스턴스 생성
mcp_server = Server("RemoteMathServer")

# 3. SSE 전송 계층 객체 생성
sse = SseServerTransport("/messages")


# 4. 도구 목록 정의
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
                "properties": {},
            },
        ),
    ]


# 5. 도구 실행 핸들러
@mcp_server.call_tool()
async def handle_call_tool(
        name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if name == "add":
        if not arguments:
            raise ValueError("Arguments required for add")
        result = calculate_sum(arguments["a"], arguments["b"])
        return [types.TextContent(type="text", text=str(result))]

    elif name == "status":
        result = get_system_status()
        return [types.TextContent(type="text", text=result)]

    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------
# ⚠️ 중요 수정 사항: 엔드포인트 정의 방식 변경
# ---------------------------------------------------------------------

async def handle_sse(request: Request):
    """Client 접속용 SSE 엔드포인트"""
    async with sse.connect_sse(
            request.scope, request.receive, request._send
    ) as streams:
        await mcp_server.run(
            streams[0], streams[1], mcp_server.create_initialization_options()
        )


async def handle_messages(request: Request):
    """
    Client 명령 수신용 엔드포인트 (Raw ASGI 방식)
    request 객체를 거치지 않고, MCP 라이브러리가 직접 소켓 입출력을 제어하게 합니다.
    """
    # return이 아니라 await로 직접 실행해야 합니다!
    return sse.handle_post_message


# 라우트 등록
app.add_route("/sse", handle_sse, methods=["GET"])
app.add_route("/messages", handle_messages, methods=["POST"])

if __name__ == "__main__":
    # worker가 1개여야 메모리 공유가 안전합니다.
    uvicorn.run(app, host="0.0.0.0", port=8081, workers=1)
