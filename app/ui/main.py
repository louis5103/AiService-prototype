import streamlit as st
import requests

# 백엔드 API 주소
BACKEND_URL = "http://localhost:8000/chat"

st.set_page_config(page_title="Gemini Agent", page_icon="🤖")
st.title("🤖 Gemini Agent with MCP Tools")

if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 입력창
if prompt := st.chat_input("무엇을 도와드릴까요?"):
    # 사용자 메시지 UI 표시
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 백엔드 호출
    with st.spinner("Agent is thinking..."):
        try:
            response = requests.post(
                BACKEND_URL,
                json={"query": prompt}
            )

            if response.status_code == 200:
                answer = response.json().get("response", "No response")
            else:
                answer = f"Error {response.status_code}: {response.text}"

        except requests.exceptions.ConnectionError:
            answer = "⚠️ 백엔드 서버(Port 8000)에 연결할 수 없습니다."

    # AI 응답 UI 표시
    st.chat_message("assistant").markdown(answer)
    st.session_state.messages.append({"role": "assistant", "content": answer})