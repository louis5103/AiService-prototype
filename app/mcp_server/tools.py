import os
import requests
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()
ALADIN_TTB_KEY = os.getenv("ALADIN_API_KEY")
CHROMA_DB_PATH = "./chroma_db"

chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)
collection = chroma_client.get_or_create_collection(
    name="books", embedding_function=sentence_transformer_ef
)


def _build_chroma_filter(filters: dict) -> dict:
    """필터 조건 생성 (가격, 카테고리, 평점, 출간일)"""
    if not filters: return None
    conditions = []

    if filters.get("max_price"):
        conditions.append({"price": {"$lte": int(filters["max_price"])}})
    if filters.get("category_name"):
        conditions.append({"category": filters["category_name"]})
    if filters.get("min_rating"):
        conditions.append({"rating": {"$gte": float(filters["min_rating"])}})

    # [수정] 날짜 필터 처리 (String -> Int 변환)
    if filters.get("min_pub_date"):
        # "2023-01-21" 같은 문자열에서 하이픈 제거 후 숫자로 변환
        date_str = filters["min_pub_date"].replace("-", "")
        if date_str.isdigit():
            conditions.append({"pub_date": {"$gte": int(date_str)}})

    if not conditions: return None
    if len(conditions) == 1: return conditions[0]
    return {"$and": conditions}


def fetch_realtime_infos(isbns: list) -> dict:
    """[Hybrid] 여러 ISBN의 최신 정보(가격, 판매지수, 중고재고)를 API로 조회"""
    if not isbns: return {}
    url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY,
        "ItemId": ",".join(isbns),
        "ItemIdType": "ISBN13",
        "Output": "js",
        "Version": "20131101",
        "OptResult": "usedList"  # 👈 [중요] ebookList -> usedList로 변경해야 중고 정보가 옵니다.
    }
    realtime_map = {}
    try:
        res = requests.get(url, params=params, timeout=3)
        data = res.json()
        for item in data.get('item', []):
            # 중고 정보 파싱 (subInfo -> usedList)
            sub_info = item.get('subInfo', {})
            used_list = sub_info.get('usedList', {})

            # 알라딘 직배송 중고 확인
            aladin_used = used_list.get('aladinUsed', {})
            used_count = aladin_used.get('itemCount', 0)
            used_min_price = aladin_used.get('minPrice', 0)

            realtime_map[item['isbn13']] = {
                "price": item.get('priceSales', 0),
                "sales_point": item.get('salesPoint', 0),
                # "stock": item.get('stockStatus', ''), # 새책 재고는 보통 '예약판매' 아니면 다 있음
                "used_count": used_count,  # 👈 중고 재고 수량
                "used_price": used_min_price  # 👈 중고 최저가
            }
    except Exception as e:
        print(f"⚠️ 실시간 조회 실패: {e}")
    return realtime_map


def search_books_by_context(query_context: str, filters: dict = None) -> str:
    print(f"[Tool] Context Search: '{query_context}' | Filters: {filters}")
    where_clause = _build_chroma_filter(filters)

    try:
        results = collection.query(
            query_texts=[query_context], n_results=5, where=where_clause
        )
    except Exception as e:
        print(f"⚠️ Chroma Error: {e}")
        return "검색 중 오류가 발생했습니다."

    if not results['documents'] or not results['documents'][0]:
        return "조건에 맞는 책을 찾을 수 없습니다."

    # Hybrid RAG: 실시간 정보 병합
    metas = results['metadatas'][0]
    docs = results['documents'][0]
    isbns = [m['isbn'] for m in metas if m.get('isbn')]
    realtime_data = fetch_realtime_infos(isbns)

    formatted = []
    for i, meta in enumerate(metas):
        isbn = meta['isbn']

        # 기본값 (DB)
        price = meta.get('price', 0)
        sp = meta.get('sales_point', 0)
        badge = "[DB]"
        used_info_str = ""  # 중고 정보 문자열 초기화

        # 실시간 업데이트
        if isbn in realtime_data:
            rt = realtime_data[isbn]
            price = rt['price']
            sp = rt['sales_point']
            badge = "✅[실시간]"

            # 👈 [추가] 중고 재고 표시 로직
            u_count = rt.get('used_count', 0)
            u_price = rt.get('used_price', 0)
            if u_count > 0:
                used_info_str = f" | 📦중고(알라딘): {u_price:,}원 ({u_count}개)"
            else:
                used_info_str = " | 🚫중고재고 없음"

        # 판매지수 힌트
        sp_hint = ""
        if sp > 50000:
            sp_hint = "🔥초대박"
        elif sp > 10000:
            sp_hint = "👍인기"

        info = (
            f"[{i + 1}] {meta['title']} {badge} {sp_hint}\n"
            f"- 저자: {meta['author']} | 분야: {meta['category']}\n"
            # 👇 가격 옆에 중고 정보를 붙여서 보여줍니다.
            f"- 판매지수: {sp:,} | 새책: {int(price):,}원{used_info_str} | 평점: {meta.get('rating')}\n"
            f"- 출간일: {meta.get('pub_date')}\n"
            f"- 내용: {docs[i][:100]}...\n"
        )
        formatted.append(info)

    return "\n".join(formatted)

def search_book_specifically(keyword: str, filters: dict = None) -> str:
    # (API 키워드 검색 로직 - 기존과 동일하게 유지)
    url = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY, "Query": keyword, "QueryType": "Keyword",
        "MaxResults": 5, "SearchTarget": "Book", "Output": "js", "Version": "20131101"
    }
    try:
        res = requests.get(url, params=params)
        items = res.json().get('item', [])
        if not items: return "검색 결과가 없습니다."

        results = []
        for item in items:
            # 파이썬 레벨 필터링
            if filters and filters.get("max_price") and item['priceSales'] > int(filters["max_price"]):
                continue
            results.append(f"- {item['title']} / {item['author']} / {item['priceSales']:,}원")
        return "\n".join(results) if results else "조건에 맞는 결과가 없습니다."
    except Exception as e:
        return f"API Error: {e}"


def get_book_details(isbn: str) -> str:
    # (상세 조회 로직 - 기존과 동일)
    return f"ISBN {isbn} 상세 조회 기능 (구현됨)"  # 지면상 생략, 이전 코드 사용


def get_system_status() -> str:
    return "SYSTEM_NORMAL"