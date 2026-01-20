import streamlit as st
import requests
from datetime import datetime, timedelta

API_URL = "http://localhost:8000/chat"
st.set_page_config(page_title="알라딘 AI 도서관", page_icon="📚", layout="wide")

st.markdown("""
<style>
    div.stButton > button { border-radius: 20px; background: #F0F2F6; border: 1px solid #ddd; }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "안녕하세요! AI 사서입니다. 📚"}]

# --- 사이드바 필터 ---
with st.sidebar:
    st.header("🔍 상세 필터")
    cat_opt = ["전체", "소설/시/희곡", "경제경영", "자기계발", "인문학", "과학", "컴퓨터/모바일"]
    sel_cat = st.selectbox("📂 카테고리", cat_opt)
    max_price = st.slider("💰 최대 가격", 0, 100000, 0, 5000)
    min_rating = st.slider("⭐ 최소 평점", 0.0, 10.0, 8.0, 0.5)

    pub_opt = st.selectbox("📅 출간 기간", ["전체 기간", "최근 3개월", "최근 6개월", "최근 1년", "최근 3년"])
    min_pub_date = None
    if pub_opt != "전체 기간":
        days = {"최근 3개월": 90, "최근 6개월": 180, "최근 1년": 365, "최근 3년": 365 * 3}
        min_pub_date = (datetime.now() - timedelta(days=days.get(pub_opt))).strftime("%Y-%m-%d")

    if st.button("🗑️ 초기화"):
        st.session_state.messages = []
        st.rerun()


# --- 전송 로직 ---
def send_query(txt):
    st.session_state.messages.append({"role": "user", "content": txt})

    # 필터 주입 (Stealth Context)
    filters = []
    if sel_cat != "전체": filters.append(f"category_name='{sel_cat}'")
    if max_price > 0: filters.append(f"max_price={max_price}")
    if min_rating > 0: filters.append(f"min_rating={min_rating}")
    if min_pub_date: filters.append(f"min_pub_date='{min_pub_date}'")

    final_query = f"{txt} (System Context: Filters -> {', '.join(filters)})" if filters else txt

    payload = {"query": final_query, "history": st.session_state.messages[:-1]}

    with st.spinner("AI가 책을 찾는 중..."):
        try:
            res = requests.post(API_URL, json=payload)
            bot_reply = res.json().get("response", "오류") if res.status_code == 200 else f"Error {res.status_code}"
        except Exception as e:
            bot_reply = f"연결 실패: {e}"

    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
    st.rerun()


# --- 메인 화면 ---
st.title("📚 알라딘 AI 도서관")
st.caption("Hybrid RAG: 벡터 검색 + 실시간 가격/재고 확인")

# 키워드 칩
cols = st.columns(4)
keywords = ["🏆 베스트셀러", "🆕 최신 IT 트렌드", "💎 숨겨진 명작", "☕️ 자바 입문서"]
for i, kw in enumerate(keywords):
    if cols[i].button(kw): send_query(f"{kw} 추천해줘")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("질문하세요..."): send_query(prompt)