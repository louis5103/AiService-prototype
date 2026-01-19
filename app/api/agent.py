import os
import json
from openai import OpenAI
from mcp import ClientSession

# 스키마 임포트
from app.api.schemas import ChatMessage
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# 환경변수 로드
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = OpenAI(
    api_key=GEMINI_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

SYSTEM_PROMPT = """
당신은 알라딘 서점의 유능한 AI 사서입니다. 
사용자의 질문을 분석하여 [맥락 추천]과 [키워드 검색]을 구분하고, 
대화 속에 숨겨진 [필터 조건]을 추출하여 도구를 호출하세요.

[도구 사용 전략]
1. 'search_books' 도구 호출 시:
   - search_type="context": "재밌는 소설 추천해줘", "자바 공부하고 싶은데" (의미/추천)
   - search_type="keyword": "한강 작가 책 찾아줘", "토비의 스프링" (정확한 검색)
   - filters: 사용자가 "3만원 이하", "IT 분야" 등을 언급하면 {'max_price': 30000} 처럼 포함.

2. 'get_details' 도구:
   - 특정 책의 상세 정보(재고, 리뷰 등)가 필요할 때 ISBN으로 호출.

[답변 스타일]
- 친절하고 전문적인 사서처럼 답변하세요.
"""


async def run_ai_agent(user_query: str, chat_history: list[ChatMessage], session: ClientSession) -> str:
    """
    main.py에서 연결된 session을 인자로 받아 로직을 수행합니다.
    """
    try:
        # 1. 도구 목록 가져오기
        mcp_tools = await session.list_tools()
        openai_tools = [{
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        } for tool in mcp_tools.tools]

        # 2. 메시지 구성
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for msg in chat_history:
            messages.append({"role": msg.role, "content": msg.content})

        # 현재 질문 추가
        messages.append({"role": "user", "content": user_query})

        # 3. 1차 LLM 호출
        response = client.chat.completions.create(
            model="gemini-2.0-flash-exp",
            messages=messages,
            tools=openai_tools,
        )

        assistant_msg = response.choices[0].message

        # 4. 도구 호출 확인
        if assistant_msg.tool_calls:
            messages.append(assistant_msg)  # 대화 맥락 유지

            for tool_call in assistant_msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except:
                    tool_args = {}

                print(f"🤖 [Agent] Tool Call: {tool_name} | Args: {tool_args}")

                # MCP 도구 실행
                result = await session.call_tool(tool_name, arguments=tool_args)
                tool_output = result.content[0].text

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output
                })

            # 5. 최종 답변 생성
            final_res = client.chat.completions.create(
                model="gemini-2.0-flash-exp",
                messages=messages
            )
            return final_res.choices[0].message.content

        return assistant_msg.content

    except Exception as e:
        print(f"❌ Agent Error: {e}")
        return "죄송합니다. 처리 중 오류가 발생했습니다."