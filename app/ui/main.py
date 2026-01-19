import streamlit as st
import requests
from datetime import datetime, timedelta  # 날짜 계산용

# ... (기본 설정 동일) ...

# --- [사이드바: 강력해진 필터] ---
with st.sidebar:
    st.header("🔍 상세 검색 필터")

    # 1. 카테고리
    category_options = ["전체", "소설/시/희곡", "경제경영", "자기계발", "인문학", "과학", "컴퓨터/모바일"]
    selected_category = st.selectbox("📂 카테고리", category_options)

    # 2. 가격
    max_price = st.slider("💰 최대 가격", 0, 100000, 0, 5000, format="%d원")

    # 3. [NEW] 평점 (최소 점수)
    min_rating = st.slider("⭐ 최소 평점", 0.0, 10.0, 8.0, 0.5)
    st.caption(f"평점 {min_rating}점 이상의 책만 검색합니다.")

    # 4. [NEW] 출간일 (최신순)
    pub_date_option = st.selectbox(
        "📅 출간 기간",
        ["전체 기간", "최근 3개월", "최근 6개월", "최근 1년", "최근 3년"]
    )

    # 날짜 계산 로직
    min_pub_date_str = None
    if pub_date_option != "전체 기간":
        today = datetime.now()
        days_map = {
            "최근 3개월": 90,
            "최근 6개월": 180,
            "최근 1년": 365,
            "최근 3년": 365 * 3
        }
        delta = days_map.get(pub_date_option, 0)
        target_date = today - timedelta(days=delta)
        min_pub_date_str = target_date.strftime("%Y-%m-%d")  # "2023-05-20" 형식

    st.divider()

    # [디버깅] 전송될 필터 미리보기
    filters_debug = []
    if selected_category != "전체": filters_debug.append(f"분야={selected_category}")
    if max_price > 0: filters_debug.append(f"가격<={max_price}")
    if min_rating > 0: filters_debug.append(f"평점>={min_rating}")
    if min_pub_date_str: filters_debug.append(f"출간일>={min_pub_date_str}")

    if filters_debug:
        st.code(" | ".join(filters_debug), language="text")
    else:
        st.text("(설정된 필터 없음)")

    if st.button("🗑️ 초기화", type="primary"):
        st.session_state.messages = []
        st.rerun()


# --- [메시지 전송 함수] ---
def send_query(text_input):
    st.session_state.messages.append({"role": "user", "content": text_input})

    # 필터 조합 (Stealth Context Injection)
    filter_list = []
    if selected_category != "전체":
        filter_list.append(f"category_name='{selected_category}'")
    if max_price > 0:
        filter_list.append(f"max_price={max_price}")
    # [NEW] 평점/날짜 추가
    if min_rating > 0:
        filter_list.append(f"min_rating={min_rating}")
    if min_pub_date_str:
        filter_list.append(f"min_pub_date='{min_pub_date_str}'")

    if filter_list:
        filter_str = ", ".join(filter_list)
        final_query = f"{text_input} (System Context: User UI Filters -> {filter_str})"
    else:
        final_query = text_input

    # ... (이하 전송 로직 동일) ...