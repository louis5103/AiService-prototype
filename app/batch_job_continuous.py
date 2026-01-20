import os
import time
import json
import requests
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# .env 로드
load_dotenv()
ALADIN_TTB_KEY = os.getenv("ALADIN_API_KEY")
CHROMA_DB_PATH = "./chroma_db"
STATE_FILE = "batch_state.json"  # 👈 여기에 마지막 페이지 번호를 저장합니다.

# 한 번 실행할 때 카테고리별로 몇 페이지씩 더 긁을지 설정
PAGES_PER_RUN = 3  # (예: 실행 시마다 분야별 3페이지씩 추가 수집)

# 수집할 카테고리 ID 목록
TARGET_CATEGORIES = {
    "종합": 0,
    "소설/시/희곡": 1,
    "경제경영": 170,
    "자기계발": 336,
    "인문학": 656,
    "과학": 987,
    "컴퓨터/모바일": 351
}


def load_state():
    """저장된 페이지 번호 상태를 불러옵니다."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    """현재 페이지 번호 상태를 파일에 저장합니다."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)


def fetch_books_by_category(category_id, page):
    """API 호출"""
    url = "http://www.aladin.co.kr/ttb/api/ItemList.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY,
        "QueryType": "Bestseller",  # 또는 ItemNewAll (신간 전체)
        "MaxResults": 50,
        "start": page,
        "SearchTarget": "Book",
        "CategoryId": category_id,
        "Output": "js",
        "Version": "20131101",
        "Cover": "Big"
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        if "item" in data:
            return data["item"]
        return []
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return []


def format_book_context(book):
    return (
        f"도서명: {book.get('title', '')}\n"
        f"저자: {book.get('author', '')}\n"
        f"장르: {book.get('categoryName', '')}\n"
        f"설명: {book.get('description', '')}"
    )


def run_continuous_batch():
    print("🚀 [Continuous Batch] 이어달리기 수집을 시작합니다...")

    # 1. DB 및 상태 로드
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="paraphrase-multilingual-MiniLM-L12-v2"
    )
    collection = client.get_or_create_collection(
        name="books",
        embedding_function=sentence_transformer_ef
    )

    state = load_state()
    total_new_books = 0

    # 2. 카테고리별 순회
    for cat_name, cid in TARGET_CATEGORIES.items():
        cid_str = str(cid)  # JSON 키는 문자열이어야 함

        # 저장된 페이지가 없으면 1페이지부터 시작
        start_page = state.get(cid_str, 1)
        end_page = start_page + PAGES_PER_RUN

        print(f"\n📂 [{cat_name}] (CID:{cid}) - {start_page}페이지부터 수집 시작...")

        current_page = start_page

        while current_page < end_page:
            books = fetch_books_by_category(cid, current_page)

            # 더 이상 데이터가 없으면 중단 (끝까지 다 긁음)
            if not books:
                print(f"   ⚠️ 더 이상 데이터가 없습니다. (Page {current_page})")
                break

            ids, documents, metadatas = [], [], []

            for book in books:
                isbn = book.get('isbn13')
                if not isbn: continue

                # [수정] 날짜 문자열("2023-01-01")을 숫자(20230101)로 변환
                raw_date = book.get('pubDate', '')
                pub_date_int = 0
                if raw_date:
                    # "-" 제거 후 정수 변환 (예: "2023-10-25" -> 20231025)
                    pub_date_int = int(raw_date.replace("-", ""))

                # 메타데이터 구성
                meta = {
                    "isbn": isbn,
                    "title": book.get('title', ''),
                    "author": book.get('author', ''),
                    "category": book.get('categoryName', ''),
                    "price": book.get('priceSales', 0),
                    "link": book.get('link', ''),
                    "rating": float(book.get('customerReviewRank', 0)),
                    "pub_date": pub_date_int  # 👈 [추가] 숫자형 날짜 저장
                }

                ids.append(isbn)
                documents.append(format_book_context(book))
                metadatas.append(meta)

            # DB 저장
            if ids:
                collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
                total_new_books += len(ids)
                print(f"   ✅ Page {current_page} 완료 ({len(ids)}권 저장)")

            # 상태 업데이트 및 저장 (중간에 꺼져도 기록되도록)
            current_page += 1
            state[cid_str] = current_page
            save_state(state)

            time.sleep(1)  # API 매너 타임

    print(f"\n🎉 [완료] 총 {total_new_books}권이 추가되었습니다.")
    print(f"💾 현재 상태가 'batch_state.json'에 저장되었습니다.")


if __name__ == "__main__":
    run_continuous_batch()