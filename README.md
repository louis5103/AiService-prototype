# 프로젝트 디렉토리 
```txt
gemini_agent_project/
├── .env                  # 환경 변수 (API KEY 등)
├── .python-version       # Python 버전 고정 (3.13.11)
├── pyproject.toml        # 의존성 및 빌드 설정
├── README.md             # 프로젝트 설명
├── uv.lock               # 버전 잠금 파일
│
└── app/                  # [Main Python Package]
    ├── __init__.py
    │
    ├── mcp/              # [MCP Server Package] 도구 제공자
    │   ├── __init__.py
    │   ├── server.py     # MCP 서버 실행 진입점 (Starlette)
    │   └── tools.py      # 실제 도구 함수들 (계산기 등)
    │
    ├── api/              # [Backend Package] FastAPI & AI Logic
    │   ├── __init__.py
    │   ├── main.py       # FastAPI 앱 실행 진입점
    │   ├── agent.py      # AI Agent 로직 (Gemini + MCP Client)
    │   └── schemas.py    # Pydantic 모델 (Request/Response 정의)
    │
    └── ui/               # [Frontend Package] Streamlit
        ├── __init__.py
        └── main.py       # Streamlit UI 코드

```

## Terminal 1 (MCP 서버 - 포트 8080)
```Bash
    uv run python -m app.mcp_server.server
```

## Terminal 2 (FastAPI 백엔드 - 포트 8000)
```Bash
    uv run python -m app.api.main
```

## Terminal 3 (Streamlit 프론트엔드 - 포트 8501)
```Bash
    uv run streamlit run app/ui/main.py
```
