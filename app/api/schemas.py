from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class QueryRequest(BaseModel):
    query: str
    history: List[ChatMessage] = []  # 이전 대화 기록 (선택 사항)