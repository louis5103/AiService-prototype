import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from app.api.schemas import QueryRequest
import app.api.agent as agent_service

MCP_SERVER_URL = "http://localhost:8081/sse"

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🔌 Connecting to MCP: {MCP_SERVER_URL}")
    try:
        async with sse_client(MCP_SERVER_URL) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                app.state.mcp_session = session
                print("✅ MCP Session Ready!")
                yield
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        yield

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat_endpoint(request: QueryRequest, req: Request):
    if not hasattr(req.app.state, "mcp_session"):
        raise HTTPException(status_code=503, detail="MCP Disconnected")
    return {"response": await agent_service.run_ai_agent(request.query, request.history, req.app.state.mcp_session)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)