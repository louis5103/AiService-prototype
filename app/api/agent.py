import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client
from fastapi import HTTPException

# 환경 변수 로드
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
MCP_SERVER_URL = "http://localhost:8080/sse"

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in .env file")

# LLM 클라이언트 설정 (Google Gemini)
client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL
)

# 전역 MCP 세션 변수
mcp_session: ClientSession | None = None
_sse_context = None  # 컨텍스트 매니저 유지를 위한 변수


async def initialize_mcp_connection():
    """MCP 서버와 연결을 수립합니다 (Lifespan에서 호출)"""
    global mcp_session, _sse_context

    try:
        # SSE 연결 시작
        _sse_context = sse_client(MCP_SERVER_URL)
        read, write = await _sse_context.__aenter__()

        # 세션 초기화
        session = ClientSession(read, write)
        await session.__aenter__()
        await session.initialize()

        mcp_session = session
        print(f"✅ Connected to MCP Server at {MCP_SERVER_URL}")

    except Exception as e:
        print(f"❌ Failed to connect to MCP Server: {e}")
        # 실제 운영시에는 여기서 재시도 로직 등이 필요할 수 있음


async def shutdown_mcp_connection():
    """MCP 서버와 연결을 종료합니다"""
    global mcp_session, _sse_context

    if mcp_session:
        await mcp_session.__aexit__(None, None, None)
    if _sse_context:
        await _sse_context.__aexit__(None, None, None)
    print("🛑 MCP Server Disconnected")


async def run_ai_agent(user_query: str) -> str:
    """사용자 질문을 받아 Gemini + MCP 도구를 활용해 답변을 생성합니다."""
    global mcp_session

    if not mcp_session:
        return "⚠️ Error: MCP Server is not connected. Please check backend logs."

    # 1. 도구 목록 조회
    tools_list = await mcp_session.list_tools()

    openai_tools = []
    for tool in tools_list.tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        })

    # 시스템 프롬프트
    # 모델에게 "도구가 필요 없으면 그냥 대화해"라고 명시적으로 지시합니다.
    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI assistant. You have access to tools, but you should only use them when necessary. If the user asks a general question (like 'Hi' or 'What is Python?'), answer directly without using tools."
        },
        {"role": "user", "content": user_query}
    ]

    print(f"🚀 [Agent] Sending query to Gemini: {user_query}")  # 로그 추가

    # 2. Gemini 1차 추론 (Reasoning)
    response = await client.chat.completions.create(
        model="gemini-2.5-flash-lite",
        messages=messages,
        tools=openai_tools,
        tool_choice="auto"
    )

    message = response.choices[0].message
    print(f"🧐 [Agent] First Response: Content={message.content}, Tool_Calls={message.tool_calls}")  # 디버깅 로그

    # 3. 도구 호출 필요 여부 확인
    if message.tool_calls:
        print("🛠️ [Agent] Tool usage detected!")
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            # MCP 서버로 도구 실행 요청
            result = await mcp_session.call_tool(func_name, arguments=func_args)

            # 대화 기록에 추가
            messages.append(message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": str(result.content)
            })

        # 4. 도구 결과를 포함하여 최종 답변 생성
        final_response = await client.chat.completions.create(
            model="gemini-2.5-flash-lite",
            messages=messages
        )
        return final_response.choices[0].message.content or "Error: Empty response after tool use."

    # 도구 호출이 없는 경우 (일반 대화)
    # message.content가 None일 수 있으므로 안전하게 처리
    if message.content:
        return message.content

    # 만약 도구도 안 부르고 내용도 없을 때.
    return "🤔 AI가 응답을 생성하지 못했습니다. (Content is None)"