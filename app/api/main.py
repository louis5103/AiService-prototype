import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI

# 내부 모듈 Import (절대 경로 사용)
from app.api.schemas import QueryRequest
from app.api.agent import run_ai_agent, initialize_mcp_connection, shutdown_mcp_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 앱 시작 시 MCP 연결
    await initialize_mcp_connection()
    yield
    # 앱 종료 시 연결 해제
    await shutdown_mcp_connection()

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(request: QueryRequest):
    answer = await run_ai_agent(request.query)
    return {"response": answer}

if __name__ == "__main__":
    # 백엔드 서버는 8000 포트 사용
    uvicorn.run(app, host="0.0.0.0", port=8000)