import os
import json
from pathlib import Path
from openai import OpenAI
from mcp import ClientSession
from dotenv import load_dotenv
from app.api.schemas import ChatMessage

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

SYSTEM_PROMPT = """
당신은 알라딘 서점의 전문 AI 사서입니다.

[핵심 역할]
1. 사용자의 질문과 제공된 'System Context(필터 정보)'를 결합하여 최적의 도구를 호출하세요.
2. 'search_books' 도구의 'filters' 인자를 적극 활용하세요.

[데이터 해석 가이드]
- 도구 결과에 '✅[실시간]' 마크가 있다면, 이는 100% 정확한 현재 정보입니다.
- '판매지수'가 50,000 이상이면 [초대박 베스트셀러], 10,000 이상이면 [스테디셀러]로 소개하세요.
- 사용자가 '최신 트렌드'를 물으면 출간일과 판매지수를 근거로 추천하세요.

[답변 스타일]
- 책 제목, 저자, 가격을 명확히 언급하고, 추천 이유를 덧붙이세요.
"""


async def run_ai_agent(user_query: str, chat_history: list[ChatMessage], session: ClientSession) -> str:
    try:
        mcp_tools = await session.list_tools()
        openai_tools = [{"type": "function",
                         "function": {"name": t.name, "description": t.description, "parameters": t.inputSchema}} for t
                        in mcp_tools.tools]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + \
                   [{"role": m.role, "content": m.content} for m in chat_history] + \
                   [{"role": "user", "content": user_query}]

        response = client.chat.completions.create(
            model="gemini-2.0-flash-exp", messages=messages, tools=openai_tools
        )
        assistant_msg = response.choices[0].message

        if assistant_msg.tool_calls:
            messages.append(assistant_msg)
            for tool_call in assistant_msg.tool_calls:
                t_name = tool_call.function.name
                t_args = json.loads(tool_call.function.arguments)
                print(f"🤖 Tool Call: {t_name} | Args: {t_args}")

                result = await session.call_tool(t_name, arguments=t_args)
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result.content[0].text})

            final_res = client.chat.completions.create(
                model="gemini-2.0-flash-exp", messages=messages
            )
            return final_res.choices[0].message.content

        return assistant_msg.content
    except Exception as e:
        print(f"❌ Error: {e}")
        return "죄송합니다, 처리 중 오류가 발생했습니다."