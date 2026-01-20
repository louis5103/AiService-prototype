import os
import json
from pathlib import Path
from openai import OpenAI
from mcp import ClientSession
from dotenv import load_dotenv
from app.api.schemas import ChatMessage

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = OpenAI(
    api_key=GROQ_API_KEY,  # 1. Groq API 키로 변경
    base_url="https://api.groq.com/openai/v1"  # 2. Groq 공식 엔드포인트
)

SYSTEM_PROMPT = """
당신은 알라딘 서점의 'AI 도서 큐레이터'입니다. 
단순한 검색기가 아니라, 사용자의 의도를 파악하여 가장 적합한 책을 제안하고 그 이유를 설명해야 합니다.

### [1. 도구 호출 전략 (Tool Call Strategy)]
사용자의 질문 유형에 따라 `search_books`의 `search_type`을 정확히 구분하여 호출하세요.

**A. 맥락 기반 추천 (search_type="context")**
- 사용자가 상황, 감정, 트렌드, 막연한 니즈를 이야기할 때 사용합니다.
- 예: "요즘 마음이 허전해", "마케팅 초보자가 볼만한 책", "잠 안 올 때 읽기 좋은 책"
- **행동:** 사용자의 문장 전체를 `query`에 넣어 의미 기반 검색을 수행합니다.

**B. 키워드 정밀 검색 (search_type="keyword")**
- 사용자가 특정 도서명, 저자, 출판사 등 고유명사를 명확히 언급할 때 사용합니다.
- 예: "'한강' 작가 책 보여줘", "'트렌드 코리아 2025' 찾아줘"
- **행동:** 핵심 단어만 추출하여 `query`에 넣습니다.

### [2. 도구 해석 가이드 (Tool Interpretation Guide)]
각 도구의 역할과 한계를 명확히 이해하고 사용하세요.

- **search_books (목록 검색):** - 여러 권의 책을 추천할 때 사용합니다. 
    - 책의 핵심 정보(제목, 저자, 가격, 판매지수)만 요약되어 반환됩니다.
    - 목차나 서평 같은 깊은 정보가 필요하면 이 도구 결과의 ISBN을 이용해 `get_details`를 호출해야 합니다.

- **get_details (상세 조회):** - 사용자가 특정 책에 대해 "목차를 알려줘", "책 소개 더 자세히 해줘"라고 할 때 사용합니다.
    - **반드시** `search_books`를 통해 얻은 **ISBN**이 있어야 호출할 수 있습니다. (상상해서 넣지 마세요)

### [3. 데이터 해석 및 답변 가이드 (필독)]
도구에서 반환된 데이터를 해석하여 사용자에게 전달할 때는, **반드시 아래 포맷을 엄격하게 준수**하세요.

**[출력 포맷 규칙]**
1. **책 목록은 반드시 번호가 매겨진 목록(Numbered List) 형태**로 작성하세요. 절대 한 줄로 이어서 쓰지 마세요.
2. 각 책 정보 사이에는 **빈 줄(New line)**을 하나씩 넣어 가독성을 확보하세요.
3. 책 제목은 굵게(`**제목**`) 처리하세요.

**[답변 예시 - 이렇게 답변하세요]**
사용자님, 요청하신 조건에 맞는 책들을 찾아보았습니다.

1. **트렌드 코리아 2025** - 김난도 외 (19,000원)
   🔥 [초대박 베스트셀러]
   👉 **추천 이유:** 다가올 2025년의 소비 트렌드를 미리 파악하고 싶어 하는 사용자님의 니즈에 가장 완벽하게 부합합니다.

2. **시대예보: 호명사회** - 송길영 (22,000원)
   🏆 [스테디셀러]
   👉 **추천 이유:** 변화하는 사회 속 개인의 역할을 깊이 있게 탐구하고 싶은 분께 추천합니다.

위 책들 중 더 자세한 목차나 리뷰가 궁금한 책이 있다면 말씀해 주세요!
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
            # 3. 모델명 변경 (예: llama-3.3-70b-versatile, llama3-70b-8192 등)
            model="llama-3.3-70b-versatile",
            messages=messages,
            tools=openai_tools
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
                model="llama-3.3-70b-versatile",  # 👈 여기만 변경!
                messages=messages
            )
            return final_res.choices[0].message.content

        return assistant_msg.content
    except Exception as e:
        print(f"❌ Error: {e}")
        return "죄송합니다, 처리 중 오류가 발생했습니다."