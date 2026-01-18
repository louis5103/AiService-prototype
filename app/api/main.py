import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

# MCP 클라이언트 모듈 (main에서 직접 연결 관리)
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

# 내부 모듈 Import
from app.api.schemas import QueryRequest
# agent 모듈 자체를 임포트하여 전역 변수(mcp_session)에 접근
import app.api.agent as agent_service

# MCP 서버 주소 (포트 8081 확인)
MCP_SERVER_URL = "http://localhost:8081/sse"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    앱의 생명주기를 관리합니다.
    async with 구문을 사용하여 MCP 연결이 끊어지지 않도록 유지합니다.
    """
    print(f"🔌 Connecting to MCP Server at {MCP_SERVER_URL}...")

    try:
        # 1. SSE 연결 수립 (async with 필수!)
        async with sse_client(MCP_SERVER_URL) as streams:
            print("✅ SSE Connection Established.")

            # 2. 세션 초기화 및 리스너 시작 (async with 필수!)
            # 이 블록이 유지되는 동안에만 메시지를 주고받을 수 있습니다.
            async with ClientSession(streams[0], streams[1]) as session:
                print("⏳ Initializing Session...")
                await session.initialize()
                print("✅ MCP Session Initialized and Ready!")

                # 3. 연결된 세션을 agent 모듈의 전역 변수에 주입
                agent_service.mcp_session = session

                # 4. 서버 실행 (여기서 멈춰서 API 요청을 처리함)
                yield

                # 5. 앱 종료 시 (자동으로 세션 정리됨)
                print("🛑 Shutting down MCP connection...")

    except Exception as e:
        print(f"❌ Failed to connect to MCP Server: {e}")
        print("⚠️ 서버는 시작되지만, AI 기능은 작동하지 않을 수 있습니다.")
        # 에러가 나도 API 서버 자체는 죽지 않도록 yield 처리
        yield


app = FastAPI(lifespan=lifespan)


@app.post("/chat")
async def chat_endpoint(request: QueryRequest):
    # agent.py의 run_ai_agent 호출 (이미 session이 주입되어 있음)
    answer = await agent_service.run_ai_agent(request.query)
    return {"response": answer}


if __name__ == "__main__":
    # 백엔드 서버는 8000 포트 사용
    uvicorn.run(app, host="0.0.0.0", port=8000)