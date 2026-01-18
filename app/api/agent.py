import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI
from mcp import ClientSession

# 환경 변수 로드
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in .env file")

# LLM 클라이언트 설정 (Google Gemini)
client = AsyncOpenAI(
    api_key=GEMINI_API_KEY,
    base_url=GEMINI_BASE_URL
)

# ✅ 전역 MCP 세션 변수
mcp_session: ClientSession | None = None


async def run_ai_agent(user_query: str) -> str:
    """사용자 질문을 받아 Gemini + MCP 도구를 활용해 답변을 생성합니다."""
    global mcp_session

    if not mcp_session:
        return "⚠️ Error: MCP Server is not connected. Please check backend logs."

    try:
        # 1. 도구 목록 조회
        print("🔍 [Agent] Fetching tools list...")
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
        messages = [
            {
                "role": "system",
                "content": "You are a helpful AI assistant. You have access to tools, but you should only use them when necessary. If the user asks a general question (like 'Hi' or 'What is Python?'), answer directly without using tools."
            },
            {"role": "user", "content": user_query}
        ]

        print(f"🚀 [Agent] Sending query to Gemini: {user_query}")

        # 2. Gemini 1차 추론 (Reasoning)
        response = await client.chat.completions.create(
            model="gemini-2.5-flash-lite",
            messages=messages,
            tools=openai_tools,
            tool_choice="auto"
        )

        message = response.choices[0].message
        print(f"🧐 [Agent] First Response: Content={message.content}, Tool_Calls={message.tool_calls}")

        # 3. 도구 호출 필요 여부 확인
        if message.tool_calls:
            print("🛠️ [Agent] Tool usage detected!")
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                # MCP 서버로 도구 실행 요청
                print(f"   -> Calling tool: {func_name} with {func_args}")
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
        if message.content:
            return message.content

        return "🤔 AI가 응답을 생성하지 못했습니다. (Content is None)"

    except Exception as e:
        print(f"❌ [Agent Error] {e}")
        return f"An error occurred while processing your request: {e}"