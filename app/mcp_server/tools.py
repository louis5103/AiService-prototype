import os
import requests
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

# .env 파일 로드 (API 키 확인)
load_dotenv()
ALADIN_TTB_KEY = os.getenv("ALADIN_API_KEY")
CHROMA_DB_PATH = "./chroma_db"

# ChromaDB 클라이언트 설정
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)
collection = chroma_client.get_or_create_collection(
    name="books",
    embedding_function=sentence_transformer_ef
)


def _build_chroma_filter(filters: dict) -> dict:
    """
    [Internal] 사용자의 필터(Dict)를 ChromaDB where 절(Dict)로 변환
    """
    if not filters:
        return None

    conditions = []

    # 1. 가격 필터 ($lte: 작거나 같음)
    if "max_price" in filters and filters["max_price"]:
        try:
            price_limit = int(filters["max_price"])
            conditions.append({"price": {"$lte": price_limit}})
        except ValueError:
            pass  # 숫자가 아니면 무시

    # 2. 카테고리 필터 (정확히 일치해야 함. 배치 작업시 저장한 카테고리명 기준)
    if "category_name" in filters and filters["category_name"]:
        conditions.append({"category": filters["category_name"]})

    if not conditions:
        return None

    # 조건이 하나면 바로 반환, 여러 개면 $and 연산
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


# --- [Tool 1] 맥락 기반 추천 (RAG + 필터링) ---
def search_books_by_context(query_context: str, filters: dict = None) -> str:
    print(f"[Tool] Context Search: '{query_context}' | Filters: {filters}")

    where_clause = _build_chroma_filter(filters)

    try:
        results = collection.query(
            query_texts=[query_context],
            n_results=5,  # 필터링으로 걸러질 수 있으니 조금 넉넉하게
            where=where_clause
        )
    except Exception as e:
        print(f"⚠️ Chroma Filter Error: {e}")
        # 필터 오류 시, 필터 없이 검색 (Fallback)
        results = collection.query(query_texts=[query_context], n_results=3)

    if not results['documents'] or not results['documents'][0]:
        return "조건에 맞는 책을 찾을 수 없습니다. (검색 결과 없음)"

    formatted_results = []
    for i in range(len(results['documents'][0])):
        meta = results['metadatas'][0][i]
        doc_snippet = results['documents'][0][i][:150]

        info = (
            f"[{i + 1}] {meta['title']} (ISBN: {meta['isbn']})\n"
            f"- 저자: {meta['author']}\n"
            f"- 분야: {meta['category']}\n"
            f"- 가격: {int(meta.get('price', 0)):,}원\n"
            f"- 요약: {doc_snippet}...\n"
        )
        formatted_results.append(info)

    return "\n".join(formatted_results)


# --- [Tool 2] 키워드 검색 (API + 필터링) ---
def search_book_specifically(keyword: str, filters: dict = None) -> str:
    print(f"[Tool] Keyword Search: '{keyword}' | Filters: {filters}")

    url = "http://www.aladin.co.kr/ttb/api/ItemSearch.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY,
        "Query": keyword,
        "QueryType": "Keyword",
        "MaxResults": 10,  # 필터링을 위해 넉넉히 가져옴
        "SearchTarget": "Book",
        "Output": "js",
        "Version": "20131101"
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()
        items = data.get('item', [])

        if not items:
            return "검색 결과가 없습니다."

        # 파이썬 레벨에서 필터링 수행
        filtered_results = []
        for item in items:
            # 가격 필터 확인
            price = item.get('priceSales', 999999)
            if filters and "max_price" in filters:
                if price > int(filters["max_price"]):
                    continue  # 가격 초과 시 스킵

            info = (
                f"- 제목: {item['title']}\n"
                f"- ISBN: {item['isbn13']}\n"
                f"- 저자: {item['author']}\n"
                f"- 가격: {price:,}원"
            )
            filtered_results.append(info)

            if len(filtered_results) >= 3:  # 3개만 추림
                break

        if not filtered_results:
            return "검색 결과는 있으나, 설정하신 가격/조건에 맞는 책이 없습니다."

        return "\n\n".join(filtered_results)

    except Exception as e:
        return f"API 검색 중 오류 발생: {str(e)}"


# --- [Tool 3] 상세 정보 조회 ---
def get_book_details(isbn: str) -> str:
    # (기존 코드와 동일)
    print(f"[Tool] Detail Lookup: {isbn}")
    url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY,
        "ItemId": isbn,
        "ItemIdType": "ISBN13",
        "Output": "js",
        "Version": "20131101",
        "OptResult": "ebookList,usedList,reviewList"
    }

    try:
        res = requests.get(url, params=params)
        data = res.json()
        if 'item' not in data: return "정보 없음"
        item = data['item'][0]

        return (
            f"[상세 정보]\n"
            f"- 제목: {item['title']}\n"
            f"- 평점: {item.get('customerReviewRank', 0)}점\n"
            f"- 전자책: {'있음' if item.get('subInfo', {}).get('ebookList') else '없음'}\n"
            f"- 중고재고: {item.get('subInfo', {}).get('usedList', {}).get('aladinUsed', {}).get('itemCount', 0)}부\n"
            f"- 소개: {item.get('description', '')[:300]}..."
        )
    except Exception as e:
        return f"오류: {e}"


def get_system_status() -> str:
    return "SYSTEM_NORMAL_OPERATION"