import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# 분리한 모듈 임포트
from app.api.schemas import QueryRequest
import app.api.agent as agent_service

# MCP 서버 주소 (server.py가 실행 중이어야 함)
MCP_SERVER_URL = "http://localhost:8081/sse"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱이 시작될 때 MCP 서버와 연결을 맺고,
    앱이 종료될 때 연결을 끊습니다.
    """
    print(f"🔌 Connecting to MCP Server at {MCP_SERVER_URL}...")
    try:
        # SSE 연결 생성
        async with sse_client(MCP_SERVER_URL) as streams:
            print("✅ SSE Connection Established.")
            # 세션 생성 및 초기화
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()

                # [핵심] 앱 상태(state)에 세션 저장 -> 어디서든 꺼내 쓸 수 있음
                app.state.mcp_session = session
                print("✅ MCP Session Ready! Server is running...")

                yield  # 여기서 서버가 계속 실행됨

                print("🛑 Shutting down MCP connection...")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        # MCP 연결 실패해도 일단 서버는 띄우되, 기능은 안 될 것임
        yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat")
async def chat_endpoint(request: QueryRequest, req: Request):
    # 1. lifespan에서 만들어둔 세션 꺼내기
    if not hasattr(req.app.state, "mcp_session"):
        raise HTTPException(status_code=503, detail="MCP Server not connected")

    session = req.app.state.mcp_session

    # 2. agent.py의 순수 로직 함수 호출 (세션 전달)
    answer = await agent_service.run_ai_agent(
        user_query=request.query,
        chat_history=request.history,
        session=session
    )

    return {"response": answer}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)