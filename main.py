import base64
import json
import os
import re
import time
from typing import Iterator

# 모듈 수준 공유 캐시 (모든 사용자 세션이 공유, TTL 1시간)
_RESPONSE_CACHE: dict[tuple, tuple[str, float]] = {}
_CACHE_TTL = 3600

import pdfplumber
import requests
import streamlit as st
import streamlit.components.v1 as components

# ─────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────
st.set_page_config(page_title="롯데캐슬스카이엘 규약 검색", page_icon="🏰", layout="centered", menu_items={})

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');

/* ── 전체 배경 (Gemini 스타일 연한 blue-gray) ── */
.stApp, [data-testid="stAppViewContainer"], section[data-testid="stMain"] {
    background: #f0f4f9 !important;
}
.main .block-container {
    background: transparent !important;
    padding-top: 0 !important;
    max-width: 780px !important;
}
[data-testid="stMainBlockContainer"] { padding-top: 0.5rem !important; }
.st-emotion-cache-zy6yx3 { padding-top: 0.5rem !important; }

/* ── 전체 폰트 ── */
html, body, * {
    font-family: 'Noto Sans KR', sans-serif !important;
}

/* ── 모든 버튼 기본: 칩 스타일 (Gemini 스타일) ── */
[data-testid="stButton"] button,
[data-testid="baseButton-primary"],
[data-testid="baseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"],
.stButton > button {
    border-radius: 12px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
    font-size: 0.9rem !important;
    font-weight: 500 !important;
    min-height: 0 !important;
    transition: background 0.15s !important;
    text-align: left !important;
    justify-content: flex-start !important;
}

/* ── secondary 버튼 = Gemini 제안 칩 ── */
[data-testid="stBaseButton-secondary"],
[data-testid="baseButton-secondary"],
[data-testid="stButton"] button[kind="secondary"] {
    background: #e9eef6 !important;
    border: none !important;
    color: #1f2937 !important;
    padding: 0.62rem 1.05rem !important;
    box-shadow: none !important;
    border-radius: 999px !important;
}
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="baseButton-secondary"]:hover {
    background: #dde3f2 !important;
}
[data-testid="stBaseButton-secondary"] p,
[data-testid="baseButton-secondary"] p,
[data-testid="stBaseButton-secondary"] span,
[data-testid="baseButton-secondary"] span {
    font-size: 0.9rem !important;
    color: #1f2937 !important;
}

/* ── primary 버튼 = 선택된 상태 (파란색) ── */
[data-testid="stBaseButton-primary"],
[data-testid="baseButton-primary"] {
    background: #d3e3fd !important;
    border: none !important;
    color: #174ea6 !important;
    padding: 0.62rem 1.05rem !important;
    box-shadow: none !important;
    border-radius: 999px !important;
}
[data-testid="stBaseButton-primary"]:hover,
[data-testid="baseButton-primary"]:hover {
    background: #c5dafc !important;
}
[data-testid="stBaseButton-primary"] p,
[data-testid="baseButton-primary"] p,
[data-testid="stBaseButton-primary"] span,
[data-testid="baseButton-primary"] span {
    color: #174ea6 !important;
    font-weight: 600 !important;
}

/* ── AI 답변 박스 ── */
[data-testid="stChatMessage"] {
    background: #ffffff !important;
    border: 1px solid #e0e6f0 !important;
    border-radius: 14px !important;
    padding: 1rem 1.2rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    gap: 0 !important;
}
[data-testid="stChatMessageAvatarAssistant"] { display: none !important; }
[data-testid="stChatMessage"] p { font-size: 0.88rem !important; line-height: 1.75 !important; margin-bottom: 0.4rem !important; }
[data-testid="stChatMessage"] li { font-size: 0.88rem !important; line-height: 1.75 !important; margin-bottom: 0.3rem !important; }
[data-testid="stChatMessage"] ul, [data-testid="stChatMessage"] ol { margin-top: 0.4rem !important; margin-bottom: 0.4rem !important; }

/* ── 채팅 입력창: Gemini 스타일 큰 카드 ── */
[data-testid="stBottom"] {
    background: transparent !important;
    padding: 0 0 10px !important;
}
[data-testid="stChatInput"] > div,
[data-testid="stChatInputContainer"] {
    border-radius: 24px !important;
    border: 1px solid #d0d7e2 !important;
    background: #ffffff !important;
    box-shadow: 0 1px 4px rgba(60,64,67,0.3), 0 4px 14px rgba(60,64,67,0.15) !important;
    padding: 11px 16px !important;
    transition: box-shadow 0.2s !important;
}
[data-testid="stChatInput"] > div:focus-within,
[data-testid="stChatInputContainer"]:focus-within {
    box-shadow: 0 4px 20px rgba(0,0,0,0.12) !important;
    border-color: #a0aabd !important;
}
[data-testid="stChatInput"] textarea {
    font-size: 0.95rem !important;
    line-height: 1.5 !important;
    color: #1a1a2e !important;
    background: transparent !important;
    border: none !important;
    outline: none !important;
    padding: 4px 0 !important;
    min-height: 30px !important;
    font-family: 'Noto Sans KR', sans-serif !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #80868b !important;
}

.gemini-topbar {
    display:flex;align-items:center;justify-content:space-between;
    padding:10px 2px 8px 2px;
}
.gemini-brand {
    display:flex;align-items:center;gap:10px;color:#3c4043;
    font-size:1.2rem;font-weight:500;letter-spacing:-0.2px;
}
.gemini-menu { color:#5f6368;font-size:1rem;padding:4px 6px;border-radius:999px; }
.gemini-right { display:flex;align-items:center;gap:8px; }

/* ── 구분선 ── */
hr { margin-top: 0.2rem !important; margin-bottom: 0.8rem !important; opacity: 0.25 !important; }

/* ── 불필요 UI 숨김 ── */
[class*="profilePreview"] { display: none !important; }
[class*="_link_gzau3"] { display: none !important; }
[class*="viewerBadge"] { display: none !important; }
#MainMenu { display: none !important; }
[data-testid="stMainMenu"] { display: none !important; }
header [data-testid="stToolbar"] { display: none !important; }
header { display: none !important; }

/* ── 팝오버 ── */
[data-testid="stPopover"] { border-radius: 14px !important; }

/* ── 다크모드 ── */
@media (prefers-color-scheme: dark) {
    .stApp, [data-testid="stAppViewContainer"], section[data-testid="stMain"] { background: #1a1c2a !important; }
    [data-testid="stBaseButton-secondary"], [data-testid="baseButton-secondary"] {
        background: #262838 !important; color: #c8ccdd !important;
    }
    [data-testid="stBaseButton-secondary"]:hover, [data-testid="baseButton-secondary"]:hover { background: #2e3045 !important; }
    [data-testid="stBaseButton-secondary"] p, [data-testid="baseButton-secondary"] p,
    [data-testid="stBaseButton-secondary"] span, [data-testid="baseButton-secondary"] span { color: #c8ccdd !important; }
    [data-testid="stChatMessage"] { background: #1c1d2c !important; border-color: #2a2c3e !important; }
    [data-testid="stChatInput"] > div, [data-testid="stChatInputContainer"] {
        background: #1e2030 !important; border-color: #3a3d52 !important;
    }
    [data-testid="stChatInput"] textarea { color: #d8daf0 !important; }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');

:root {
    color-scheme: light;
}
.stApp, [data-testid="stAppViewContainer"], section[data-testid="stMain"] {
    background: #f7f2e8 !important;
}
.main .block-container,
[data-testid="stMainBlockContainer"] {
    max-width: 780px !important;
    padding-top: 0 !important;
    padding-bottom: 8rem !important;
}
[data-testid="stAppViewBlockContainer"],
[data-testid="stVerticalBlock"] {
    padding-top: 0 !important;
}
html, body, * {
    font-family: Pretendard, 'Noto Sans KR', sans-serif !important;
    letter-spacing: 0 !important;
}
hr { display: none !important; }

.sky-topbar {
    display: inline-flex;
    align-items: center;
    gap: 12px;
    margin-top: -4.05rem !important;
    padding: 0 !important;
    color: #32281b !important;
    text-decoration: none !important;
}
.sky-logo {
    width: 34px;
    height: 34px;
    object-fit: contain;
    display: block;
}
.sky-brand-title {
    font-size: 1.23rem;
    font-weight: 700;
    color: #34291d;
    line-height: 1.1;
}
.sky-home {
    padding: 1.15rem 0 1.2rem !important;
}
.sky-hello {
    margin: 0 0 0.52rem;
    color: #8a7359;
    font-size: 1.02rem;
    font-weight: 500;
}
.sky-question {
    margin: 0 !important;
    color: #2e251a !important;
    font-size: clamp(1.78rem, 5.2vw, 2.7rem) !important;
    font-weight: 720 !important;
    line-height: 1.05 !important;
    white-space: nowrap !important;
}
.sky-guide {
    margin: 0.7rem 0 0 !important;
    color: rgba(92, 73, 51, 0.56) !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
}
.sky-source-title {
    margin: 1.1rem 0 0.55rem;
    color: #5c4933;
    font-size: 0.94rem;
    font-weight: 700;
}

[data-testid="stBottom"] {
    background: linear-gradient(180deg, rgba(247,242,232,0), #f7f2e8 22%) !important;
    padding: 10px 0 14px !important;
}
.st-key-sky_mode_bar {
    width: min(680px, calc(100vw - 48px));
    position: fixed;
    left: 50%;
    bottom: 142px;
    transform: translateX(-50%);
    z-index: 999991;
    margin: 0;
    background: transparent !important;
}
.st-key-sky_mode_bar [data-testid="stElementToolbar"] {
    display: none !important;
}
.st-key-sky_mode_bar [data-testid="stButtonGroup"] {
    display: flex !important;
    gap: 6px !important;
    flex-wrap: wrap !important;
    justify-content: flex-start !important;
}
.st-key-sky_mode_bar button {
    border-radius: 999px !important;
    min-height: 30px !important;
    padding: 0.34rem 0.68rem !important;
    border: 1px solid rgba(104, 82, 51, 0.18) !important;
    background: rgba(255,255,255,0.56) !important;
    color: #8f7c67 !important;
    box-shadow: none !important;
}
.st-key-sky_mode_bar button p,
.st-key-sky_mode_bar button span {
    font-size: 0.78rem !important;
    font-weight: 520 !important;
    color: inherit !important;
}
.st-key-sky_mode_bar button[kind="pillsActive"],
.st-key-sky_mode_bar button[aria-pressed="true"] {
    background: #5c4933 !important;
    border-color: #5c4933 !important;
    color: #fff8ed !important;
}

[data-testid="stChatInput"] > div,
[data-testid="stChatInputContainer"] {
    width: min(680px, calc(100vw - 48px)) !important;
    margin: 0 auto !important;
    min-height: 58px !important;
    max-height: 58px !important;
    border-radius: 18px !important;
    border: 1px solid rgba(109, 84, 50, 0.20) !important;
    background: rgba(255,255,255,0.92) !important;
    box-shadow: 0 8px 28px rgba(67, 49, 27, 0.13), 0 1px 2px rgba(67, 49, 27, 0.08) !important;
    padding: 12px 48px 12px 16px !important;
    position: relative !important;
}
[data-testid="stChatInput"] textarea {
    min-height: 32px !important;
    height: 32px !important;
    max-height: 32px !important;
    overflow-y: auto !important;
    resize: none !important;
    font-size: 0.9rem !important;
    line-height: 1.45 !important;
    color: #2d2419 !important;
    padding: 5px 0 !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: rgba(72, 58, 41, 0.38) !important;
    font-size: 0.8rem !important;
}
[data-testid="stChatInput"] textarea:focus::placeholder {
    color: transparent !important;
}
[data-testid="stChatInput"] button {
    position: absolute !important;
    right: 12px !important;
    top: 50% !important;
    transform: translateY(-50%) !important;
}

.sky-result-summary {
    margin: 0 0 0.7rem;
    padding: 0.74rem 0.9rem;
    border: 1px solid rgba(104, 82, 51, 0.14);
    border-radius: 12px;
    background: rgba(255,255,255,0.58);
    color: #4f3d29;
    font-size: 0.92rem;
}
.sky-empty {
    text-align: center;
    color: #8b7a65;
    padding: 2.5rem 0;
    font-size: 0.92rem;
}

@media (max-width: 640px) {
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-left: 18px !important;
        padding-right: 18px !important;
    }
    .st-key-sky_mode_bar {
        width: min(680px, calc(100vw - 36px));
        bottom: 142px;
    }
    .st-key-sky_mode_bar [data-testid="stButtonGroup"] {
        justify-content: center !important;
    }
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInputContainer"] {
        width: min(680px, calc(100vw - 36px)) !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* Streamlit Cloud/브라우저 다크 테마가 섞여 들어와도 화면은 하나의 라이트 톤으로 고정 */
html,
body,
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"],
[data-testid="stMainBlockContainer"] {
    background: #f7f2e8 !important;
    color: #2e251a !important;
}

[data-testid="stBottom"],
[data-testid="stBottom"] > div,
[data-testid="stBottomBlockContainer"],
[data-testid="stBottomBlockContainer"] > div {
    background: linear-gradient(180deg, rgba(247,242,232,0), #f7f2e8 26%) !important;
}

[data-testid="stBottom"] [data-testid="stChatInput"] > div,
[data-testid="stBottom"] [data-testid="stChatInputContainer"],
[data-testid="stChatInput"] > div,
[data-testid="stChatInputContainer"],
[data-baseweb="textarea"],
[data-baseweb="textarea"] > div {
    background: #fffdfa !important;
    color: #2d2419 !important;
}

[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] textarea:focus,
[data-testid="stChatInput"] textarea:active {
    background: transparent !important;
    color: #2d2419 !important;
    caret-color: #5c4933 !important;
}

[data-testid="stChatInput"] button {
    background: #eee8dd !important;
    color: #5c4933 !important;
}
[data-testid="stChatInput"] button:enabled {
    background: #5c4933 !important;
    color: #fff8ed !important;
}

[data-testid="stChatMessage"] {
    background: #fffdf8 !important;
    border: 1px solid rgba(104,82,51,0.14) !important;
    color: #2d2419 !important;
    box-shadow: 0 4px 14px rgba(67,49,27,0.07) !important;
}
[data-testid="stChatMessage"] *,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] strong,
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    color: #2d2419 !important;
}
[data-testid="stExpander"] {
    background: #fffaf1 !important;
    border: 1px solid rgba(104,82,51,0.16) !important;
    color: #2d2419 !important;
}
[data-testid="stExpander"] * {
    color: #2d2419 !important;
}
</style>
""", unsafe_allow_html=True)

if st.query_params.get("home") == "1":
    for _k in ["in_chat", "keyword_results", "keyword_query", "keyword_terms", "messages_by_doc"]:
        st.session_state.pop(_k, None)
    st.session_state.search_mode = "keyword"
    st.query_params.clear()
    st.rerun()

# ── 헤더: 로고/텍스트 클릭 시 홈으로 이동 ──
try:
    with open("logo.png", "rb") as f:
        _logo_b64 = base64.b64encode(f.read()).decode()
    _logo_sm = (
        f"<img src='data:image/png;base64,{_logo_b64}' "
        "class='sky-logo'>"
    )
except Exception:
    _logo_sm = "<span class='sky-logo' style='font-size:1.55rem;line-height:34px'>🏰</span>"

st.markdown(
    f"<a class='sky-topbar' href='?home=1' target='_self'>"
    f"{_logo_sm}<span class='sky-brand-title'>원당역 롯데캐슬스카이엘</span>"
    f"</a>",
    unsafe_allow_html=True,
)

st.markdown("<hr>", unsafe_allow_html=True)

# ─────────────────────────────────────────
# ⚙️ 컨텍스트 압축 설정
# ─────────────────────────────────────────
USE_CONTEXT_COMPRESSION = True
MAX_ARTICLES_IN_CONTEXT = 20

# ─────────────────────────────────────────
# 1. API 키
# ─────────────────────────────────────────
try:
    st.session_state["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
    api_ready = True
except Exception:
    st.warning("⚠️ Streamlit Cloud의 Settings > Secrets에 GOOGLE_API_KEY를 등록해주세요.")
    api_ready = False

# ─────────────────────────────────────────
# 2. PDF 로드
# ─────────────────────────────────────────
def is_toc_page(text: str) -> bool:
    return text.count("·") + text.count("…") + text.count("‥") > 8

@st.cache_data(show_spinner=False)
def load_pdf_text(pdf_path: str, _v: int = 1) -> str:
    if not os.path.exists(pdf_path):
        return ""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                if not is_toc_page(text):
                    pages.append(text)
    except Exception as e:
        st.error(f"PDF 읽기 오류 ({pdf_path}): {e}")
    return "\n\n".join(pages)

@st.cache_data(show_spinner=False)
def load_text_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# ─────────────────────────────────────────
# 3. 문서 로드
# ─────────────────────────────────────────
PDF_FILES = {
    "주차규약":         "rules_parking.pdf",
    "커뮤니티센터 규약": "rules_community.pdf",
}

TEXT_FILES = {
    "관리규약": "rules_management.txt",
    "생활안내": "입주안내문_전체.txt",
}

# 압축 적용 대상 (전문이 긴 규약)
COMPRESSION_TARGET_DOCS = {"관리규약"}

pdf_texts: dict[str, str] = {}

for name, path in PDF_FILES.items():
    t = load_pdf_text(path)
    if t:
        pdf_texts[name] = t

for name, path in TEXT_FILES.items():
    t = load_text_file(path)
    if t:
        pdf_texts[name] = t

if not pdf_texts:
    st.error("📂 GitHub 저장소에 PDF 파일을 업로드해주세요.")
    st.stop()

# ─────────────────────────────────────────
# 4. 공통 상수
# ─────────────────────────────────────────
DOC_ORDER = [n for n in ["주차규약", "커뮤니티센터 규약", "관리규약", "생활안내"] if n in pdf_texts]

if "selected_doc" not in st.session_state or st.session_state.selected_doc not in DOC_ORDER:
    st.session_state.selected_doc = DOC_ORDER[0]
if "search_mode" not in st.session_state:
    st.session_state.search_mode = "keyword"

# ─────────────────────────────────────────
# 5. Gemini AI
# ─────────────────────────────────────────
def ai_generate(prompt: str) -> str:
    api_key  = st.session_state.get("GOOGLE_API_KEY", "")
    model    = "gemini-2.5-flash"
    url     = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 4096, "thinkingConfig": {"thinkingBudget": 0}},
    }
    last_err = ""
    last_status = 0
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 429:
            last_err = resp.text
            last_status = 429
            time.sleep((attempt + 1) * 15)
            continue
        if resp.status_code in (500, 502, 503, 504):
            last_err = resp.text
            last_status = resp.status_code
            time.sleep((attempt + 1) * 5)
            continue
        if not resp.ok:
            raise RuntimeError(f"API 오류 {resp.status_code}: {resp.text}")
        candidate = resp.json()["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]
        if candidate.get("finishReason") == "MAX_TOKENS":
            cont = requests.post(url, headers=headers, json={
                "contents": [
                    {"role": "user",  "parts": [{"text": prompt}]},
                    {"role": "model", "parts": [{"text": text}]},
                    {"role": "user",  "parts": [{"text": "이어서 계속 작성해줘."}]},
                ],
                "generationConfig": {"maxOutputTokens": 4096},
            }, timeout=120)
            if cont.ok:
                text += cont.json()["candidates"][0]["content"]["parts"][0]["text"]
        return text
    raise RuntimeError(f"API {last_status} 오류 (3회 재시도 실패): {last_err}")

def ai_generate_stream(prompt: str) -> Iterator[str]:
    """Gemini SSE 스트리밍. 토큰 조각을 순차적으로 yield.
    429/5xx는 연결 수립 전까지 최대 3회 재시도. MAX_TOKENS이면 이어쓰기 1회 수행.
    """
    api_key  = st.session_state.get("GOOGLE_API_KEY", "")
    model    = "gemini-2.5-flash"
    stream_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:streamGenerateContent?alt=sse"
    )
    cont_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 4096, "thinkingConfig": {"thinkingBudget": 0}},
    }
    last_err = ""
    last_status = 0
    for attempt in range(3):
        resp = requests.post(stream_url, headers=headers, json=payload, timeout=120, stream=True)
        if resp.status_code == 429:
            last_err = resp.text
            last_status = 429
            time.sleep((attempt + 1) * 15)
            continue
        if resp.status_code in (500, 502, 503, 504):
            last_err = resp.text
            last_status = resp.status_code
            time.sleep((attempt + 1) * 5)
            continue
        if not resp.ok:
            raise RuntimeError(f"API 오류 {resp.status_code}: {resp.text}")

        accumulated = ""
        last_finish = None
        for raw_line in resp.iter_lines(decode_unicode=False):
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                obj = json.loads(data)
            except Exception:
                continue
            cands = obj.get("candidates") or []
            if not cands:
                continue
            cand = cands[0]
            for p in cand.get("content", {}).get("parts", []) or []:
                t = p.get("text")
                if t:
                    accumulated += t
                    yield t
            if "finishReason" in cand:
                last_finish = cand["finishReason"]

        if last_finish == "MAX_TOKENS" and accumulated:
            try:
                cont = requests.post(cont_url, headers=headers, json={
                    "contents": [
                        {"role": "user",  "parts": [{"text": prompt}]},
                        {"role": "model", "parts": [{"text": accumulated}]},
                        {"role": "user",  "parts": [{"text": "이어서 계속 작성해줘."}]},
                    ],
                    "generationConfig": {"maxOutputTokens": 4096},
                }, timeout=120)
                if cont.ok:
                    tail = cont.json()["candidates"][0]["content"]["parts"][0]["text"]
                    if tail:
                        yield tail
            except Exception:
                pass
        return
    raise RuntimeError(f"API {last_status} 오류 (3회 재시도 실패): {last_err}")

def ai_generate_smart_stream(prompt: str) -> Iterator[str]:
    """스트리밍을 시도하고, 실패하거나 토큰이 하나도 안 오면 non-stream으로 자동 폴백."""
    stream_err: Exception | None = None
    any_yielded = False
    try:
        for chunk in ai_generate_stream(prompt):
            if chunk:
                any_yielded = True
                yield chunk
    except Exception as e:
        stream_err = e

    if any_yielded:
        return

    # 스트리밍 실패 또는 0 토큰 → non-stream 폴백
    try:
        text = ai_generate(prompt)
    except Exception:
        if stream_err is not None:
            raise stream_err
        raise
    if text:
        yield text

def friendly_error_message(exc: Exception) -> str:
    msg = str(exc)
    if "429" in msg:
        return "⏳ 잠시 요청이 많습니다. 10~20초 후 다시 시도해 주세요."
    if any(code in msg for code in ("500", "502", "503", "504")):
        return "🔧 AI 서버가 일시적으로 혼잡합니다. 잠시 후 다시 시도해 주세요."
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "⏱️ 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요."
    if "ConnectionError" in msg or "ConnectTimeout" in msg:
        return "🌐 네트워크 연결에 문제가 있습니다. 잠시 후 다시 시도해 주세요."
    return "⚠️ 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

def split_body_and_citations(text: str) -> tuple[list[str], list[str]]:
    body, cites = [], []
    for line in text.split("\n"):
        (cites if line.strip().startswith("📌") else body).append(line)
    return body, cites

# ─────────────────────────────────────────
# 6. 조항 파싱 (규약 PDF용)
# ─────────────────────────────────────────
ARTICLE_RE = re.compile(
    r"(제\s*\d+\s*조[^\n]*(?:\n(?!제\s*\d+\s*조).+)*)",
    re.MULTILINE
)
TITLE_RE = re.compile(
    r"제\s*(\d+)\s*조(?:의\s*\d+)?"
    r"(?:\s*【([^】]*)】|\s*\(([^\)]{1,20})\)|\s+([가-힣a-zA-Z\s·,]{2,20}?))?"
)
# 관리규약 텍스트 파일용: 제N조【제목】 또는 제N조(제목) 형식만 유효 조항으로 인정
_VALID_ARTICLE_RE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*[【\(]")

def extract_title(first_line: str) -> str:
    tm = TITLE_RE.match(first_line)
    if not tm:
        return first_line[:30].strip()
    num = tm.group(1)
    sub = (tm.group(2) or tm.group(3) or tm.group(4) or "").strip()
    if tm.group(4):
        sub = sub.split(" ")[0] if len(sub) > 10 else sub
    return f"제{num}조" + (f" {sub}" if sub else "")

def parse_articles(doc_name: str, text: str) -> list[dict]:
    articles = []
    for m in ARTICLE_RE.finditer(text):
        block = m.group(0).strip()
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        first = lines[0].strip()
        # 관리규약(텍스트): 제N조【】 또는 제N조() 형식만 허용
        if doc_name == "관리규약" and not _VALID_ARTICLE_RE.match(first):
            continue
        # 기존 로직: 1줄짜리는 내용이 너무 짧으면 스킵 (관리규약은 1줄 조항도 허용)
        if len(lines) <= 1 and doc_name != "관리규약":
            continue
        title = extract_title(first)
        if len(block) > 1500:
            block = block[:1500].strip() + "...(이하 생략)"
        articles.append({"doc": doc_name, "title": title, "content": block})
    return articles

def parse_attachments(doc_name: str, text: str) -> list[dict]:
    results = []
    pat = re.compile(
        r"((?:(?:▣\s*)?첨부\s*#\d+|<별표\s*\d+>|\[별표\s*\d+\])[^\n]*(?:\n(?!(?:(?:▣\s*)?첨부\s*#\d+|<별표\s*\d+>|\[별표\s*\d+\])).+)*)",
        re.MULTILINE
    )
    for m in pat.finditer(text):
        block = m.group(0).strip()
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) <= 1:
            continue
        title = lines[0].strip().replace("▣", "").strip()
        if len(block) > 1500:
            block = block[:1500].strip() + "...(이하 생략)"
        results.append({"doc": doc_name, "title": title, "content": block})
    return results

# ─────────────────────────────────────────
# 7. 섹션 파싱 (생활안내 텍스트 파일용)
# ─────────────────────────────────────────
SECTION_RE = re.compile(r"={3,}\s*(.+?)\s*={3,}", re.MULTILINE)

def parse_sections(doc_name: str, text: str) -> list[dict]:
    """===== 섹션명 ===== 단위로 파싱"""
    sections = []
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if not content:
            continue
        # 섹션 내 번호 항목(1. 2. 3.)도 서브 아이템으로 추가
        sections.append({
            "doc": doc_name,
            "title": title,
            "content": content,
        })
        # 번호 항목 단위 서브 파싱
        sub_items = parse_numbered_items(doc_name, title, content)
        sections.extend(sub_items)
    return sections

def parse_numbered_items(doc_name: str, parent_title: str, text: str) -> list[dict]:
    """1. 항목명 단위로 서브 파싱"""
    items = []
    pat = re.compile(r"^(\d+\.\s+.+?)(?=\n\d+\.\s|\Z)", re.MULTILINE | re.DOTALL)
    for m in pat.finditer(text):
        block = m.group(0).strip()
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) <= 1:
            continue
        title = lines[0].strip()
        items.append({
            "doc": doc_name,
            "title": f"{parent_title} > {title}",
            "content": block,
        })
    return items

@st.cache_data(show_spinner=False)
def get_articles(doc_name: str, text: str, _v: int = 2) -> list[dict]:
    if doc_name == "생활안내":
        return parse_sections(doc_name, text)
    arts = parse_articles(doc_name, text)
    arts += parse_attachments(doc_name, text)
    return arts

# ─────────────────────────────────────────
# 8. 컨텍스트 압축
# ─────────────────────────────────────────
_STOPWORDS = {
    "은", "는", "이", "가", "을", "를", "의", "에", "서", "도", "만",
    "로", "으로", "와", "과", "한", "하다", "있다", "없다", "되다",
    "하면", "되면", "인지", "어떤", "어떻게", "무엇", "언제", "어디",
    "뭐야", "뭐", "인가", "나요", "까요", "예요", "이에요", "있나요",
    "있어요", "없나요", "알려줘", "알려주세요", "궁금해", "궁금합니다",
}

# 주민들이 자주 쓰는 줄임말 → 규약 원문 용어 매핑
_SYNONYMS = {
    "동대표": "동별 대표자",
    "대표회의": "입주자대표회의",
    "관리비": "관리비",
    "장기수선": "장기수선충당금",
    "관리소": "관리사무소",
    "관리소장": "관리사무소장",
    "주차장": "주차시설",
    "놀이터": "어린이놀이터",
    "헬스장": "주민운동시설",
    "커뮤니티": "주민공동시설",
    # 주차규약
    "오토바이": "이륜자동차",
    "바이크": "이륜자동차",
    "렌트카": "대체차량",
    # 커뮤니티센터 규약
    "사우나": "목욕탕",
    "골프장": "골프 연습장",
    "도서관": "작은 도서관",
    # 공통
    "엘리베이터": "승강기",
    "전기차": "전기자동차",
    "입주민": "입주자",
}

def extract_keywords(question: str) -> list[str]:
    words = re.findall(r"[가-힣a-zA-Z0-9]{2,}", question)
    filtered = [w for w in words if w not in _STOPWORDS]
    expanded = []
    for w in filtered:
        expanded.append(w)
        for syn_key, syn_val in _SYNONYMS.items():
            if syn_key in w and syn_val not in expanded:
                expanded.append(syn_val)
    return expanded

def score_article(art: dict, keywords: list[str]) -> int:
    score = 0
    title_lower = art["title"].lower()
    content_lower = art["content"].lower()
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            score += 3
        elif kw_lower in content_lower:
            score += 1
    return score

def build_compressed_context_pdf(doc_name: str, question: str, all_arts: list[dict]) -> str:
    """규약 PDF용: 관련 조항만 추려서 전송"""
    keywords = extract_keywords(question)
    if not keywords:
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    scored = []
    for art in all_arts:
        if art["doc"] != doc_name:
            continue
        s = score_article(art, keywords)
        if s > 0:
            scored.append((s, art))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_arts = [art for _, art in scored[:MAX_ARTICLES_IN_CONTEXT]]

    if not top_arts:
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    def art_sort_key(a):
        m = re.search(r"제\s*(\d+)\s*조", a["title"])
        return int(m.group(1)) if m else 9999

    top_arts.sort(key=art_sort_key)

    ctx_parts = [f"=== [{doc_name}] (관련 조항 {len(top_arts)}개) ==="]
    for art in top_arts:
        ctx_parts.append(art["content"])

    return "\n\n".join(ctx_parts)

def build_compressed_context_guide(doc_name: str, question: str, all_arts: list[dict]) -> str:
    """생활안내 텍스트용: 관련 섹션만 추려서 전송
    - 섹션 단위(===== =====) 아이템만 사용 (서브 아이템 중복 제외)
    - 점수 높은 순으로 최대 5개 섹션 전송
    """
    keywords = extract_keywords(question)

    # 섹션 단위 아이템만 (title에 > 없는 것 = 최상위 섹션)
    section_arts = [a for a in all_arts if a["doc"] == doc_name and " > " not in a["title"]]

    if not keywords or not section_arts:
        # 키워드 없거나 파싱 실패 시 전문 전송
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    scored = []
    for art in section_arts:
        s = score_article(art, keywords)
        scored.append((s, art))

    scored.sort(key=lambda x: x[0], reverse=True)

    # 점수 0인 것도 일부 포함 (혹시 키워드 매칭 안 됐을 때 대비해 상위 3개는 무조건)
    top_arts = [art for _, art in scored[:5] if scored[0][0] > 0]

    if not top_arts:
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    ctx_parts = [f"=== [{doc_name}] (관련 섹션 {len(top_arts)}개) ==="]
    for art in top_arts:
        ctx_parts.append(f"[ {art['title']} ]\n{art['content']}")

    return "\n\n".join(ctx_parts)

def get_context_for_ai(doc_name: str, question: str, all_arts: list[dict]) -> str:
    if not USE_CONTEXT_COMPRESSION:
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    if doc_name == "생활안내":
        return build_compressed_context_guide(doc_name, question, all_arts)

    if doc_name in COMPRESSION_TARGET_DOCS:
        return build_compressed_context_pdf(doc_name, question, all_arts)

    return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

# ─────────────────────────────────────────
# 9. 근거 조항 추출 (AI 응답 → 규약명+조번호)
# ─────────────────────────────────────────
DOC_PAT = re.compile(
    r"(관리규약"
    r"|주차\s*관리\s*규정?"
    r"|주차\s*규약"
    r"|커뮤니티\s*센터?\s*규약"
    r"|주민공동시설\s*운영규정?"
    r"|운영규정"
    r"|생활안내"
    r"|입주안내)"
)

def classify_doc(raw: str) -> str:
    if "관리규약" in raw and "주차" not in raw:
        return "관리규약"
    if "주차" in raw:
        return "주차규약"
    if "생활안내" in raw or "입주안내" in raw:
        return "생활안내"
    return "커뮤니티센터 규약"

def extract_pairs(txt: str) -> list[tuple]:
    result = []
    clean  = re.sub(r"[^\w\s가-힣]", " ", txt)
    for dm in DOC_PAT.finditer(clean):
        doc_name = classify_doc(dm.group(0))
        after    = clean[dm.end():]
        nxt      = DOC_PAT.search(after)
        scope    = after[:nxt.start()] if nxt else after
        for am in re.finditer(r"제\s*(\d+)\s*조", scope):
            result.append((doc_name, am.group(1)))
    return list(dict.fromkeys(result))

def find_related_articles(response_text: str, all_arts: list[dict], doc_name: str) -> list[dict]:
    related   = []
    seen_keys = set()

    anchor_text = " ".join(re.findall(r"📌\s*([^\n]+)", response_text))
    search_text = anchor_text if anchor_text else response_text

    # 규약 문서: 조항 번호 매칭
    for dn, num in extract_pairs(search_text):
        key = (dn, num)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        pat = re.compile(rf"제\s*{num}\s*조")
        for art in all_arts:
            if art["doc"] == dn and pat.search(art["title"]):
                related.append(art)
                break

    # 첨부/별표 매칭
    attach_pat = re.compile(r"첨부\s*#(\d+)")
    for am in attach_pat.finditer(search_text):
        attach_title = f"첨부 #{am.group(1)}"
        for art in all_arts:
            if attach_title in art["title"] and art not in related:
                related.append(art)
                break

    byulpyo_pat = re.compile(
        r"(관리규약|주차규약|커뮤니티센터\s*규약).*?별표\s*(\d+)"
        r"|별표\s*(\d+)"
    )
    for bm in byulpyo_pat.finditer(search_text):
        raw_doc = (bm.group(1) or "").strip()
        num = bm.group(2) or bm.group(3)
        dn = classify_doc(raw_doc) if raw_doc else None
        for art in all_arts:
            if dn and art["doc"] != dn:
                continue
            if re.search(rf"별표\s*{num}", art["title"]) and len(art["title"]) > 10 and art not in related:
                related.append(art)
                break

    # 생활안내: 섹션 키워드 매칭
    if doc_name == "생활안내":
        keywords = extract_keywords(search_text)
        section_arts = [a for a in all_arts if a["doc"] == "생활안내" and " > " not in a["title"]]
        for art in section_arts:
            if art in related:
                continue
            if any(kw.lower() in art["title"].lower() or kw.lower() in art["content"].lower()
                   for kw in keywords):
                related.append(art)
                if len(related) >= 5:
                    break

    return related

# ─────────────────────────────────────────
# 9-1. 📌 근거 한 줄 합치기
# ─────────────────────────────────────────
def _collapse_citations(text: str) -> str:
    """여러 줄의 📌 근거를 같은 규약끼리 한 줄로 합친다.
    예: 📌 관리규약 제3조 / 📌 관리규약 제18조 → 📌 관리규약 제3조, 제18조
    """
    lines = text.split("\n")
    body_lines = []
    citation_lines = []

    for line in lines:
        if line.strip().startswith("📌"):
            citation_lines.append(line.strip())
        else:
            body_lines.append(line)

    if not citation_lines:
        return text

    # 규약별로 그룹핑
    from collections import OrderedDict
    groups: OrderedDict[str, list[str]] = OrderedDict()
    for cl in citation_lines:
        raw = cl.lstrip("📌").strip()
        # "관리규약 제3조" → doc="관리규약", detail="제3조"
        m = re.match(r"(관리규약|주차규약|커뮤니티센터\s*규약|생활안내)\s*(.*)", raw)
        if m:
            doc = m.group(1).strip()
            detail = m.group(2).strip()
            if doc not in groups:
                groups[doc] = []
            if detail and detail not in groups[doc]:
                groups[doc].append(detail)
        else:
            if raw not in groups:
                groups[raw] = []

    # 한 줄씩 합치기
    merged = []
    for doc, details in groups.items():
        if details:
            merged.append(f"📌 {doc} {', '.join(details)}")
        else:
            merged.append(f"📌 {doc}")

    # body 끝의 빈 줄 정리 후 근거 붙이기
    body = "\n".join(body_lines).rstrip()
    return body + "\n\n" + "\n".join(merged)

# ─────────────────────────────────────────
# 9-b. 주차 요금표 (별표1) — PDF 표 미인식 보완용 하드코딩
# ─────────────────────────────────────────
_PARKING_FEE_SUPPLEMENT = """
[별표1 주차시설 사용료 — PDF 표 직접 데이터]
※ PDF 표가 자동 추출되지 않으므로 아래 데이터를 반드시 참조할 것.
※ 별표1은 공급면적(전용면적+주거공용면적) 기준으로 계산됨.

▶ 기본 원칙
- 1호차(세대당 첫 번째 등록 차량): 무료
- 2호차: 아래 별표1 기준 월 사용료
- 3호차 이상 (보장 주차면 초과 1대당): 월 150,000원

▶ 세대 타입별 2호차 월 사용료 (공급면적 기준, 정확한 값)
- 35㎡ (약 17평, 공급면적 55.29㎡, 124세대) → 월 23,600원
- 47㎡ (약 22평, 공급면적 72.37㎡, 26세대) → 월 18,600원
- 59㎡ A타입 (약 24평, 공급면적 81.57㎡, 463세대) → 월 15,800원
- 59㎡ B타입 (약 24평, 공급면적 82.08㎡, 262세대) → 월 15,600원
- 74㎡ (약 30평, 공급면적 100.62㎡, 93세대) → 월 10,200원
- 84㎡ A타입 (약 33평, 공급면적 109.55㎡, 247세대) → 월 7,600원
- 84㎡ B타입 (약 33평, 공급면적 110.08㎡, 21세대) → 월 7,400원
※ 사용자가 "24평", "33평" 등으로 질문하면 위 평형 기준으로 해당 타입을 찾아 답변할 것
※ 위 7개 타입 외 다른 평형은 이 단지에 존재하지 않음

▶ 별표1 전체 데이터 (공급면적 → 월 요금)
27.7576㎡→34,000원 / 29.2855㎡→33,600원 / 34.2672㎡→32,400원 /
35.2865㎡→32,200원 / 36.4628㎡→32,000원 / 43.3803㎡→30,400원 /
44.4170㎡→30,200원 / 44.6842㎡→30,200원 / 45.0040㎡→30,200원 /
46.1739㎡→29,800원 / 47.7808㎡→29,600원 / 48.4193㎡→29,400원 /
51.1295㎡→28,800원 / 55.2918㎡→23,600원 / 59.3659㎡→27,000원 /
60.5273㎡→26,800원 / 60.5388㎡→26,800원 / 60.7956㎡→26,600원 /
62.5448㎡→26,200원 / 66.6151㎡→25,400원 / 67.0096㎡→25,400원 /
67.1853㎡→25,200원 / 72.3662㎡→18,600원 / 73.9066㎡→23,800원 /
79.5741㎡→22,600원 / 80.3749㎡→22,400원 / 81.5672㎡→15,800원 /
82.0757㎡→15,600원 / 93.9744㎡→19,400원 / 100.6207㎡→10,200원 /
109.5464㎡→7,600원 / 110.0786㎡→7,400원 / 132.9927㎡→10,800원
""".strip()

# ─────────────────────────────────────────
# 10. 카드 렌더링
# ─────────────────────────────────────────
DOC_COLORS = {
    "관리규약":         "#9a3412",
    "주차규약":         "#166534",
    "커뮤니티센터 규약": "#1d4ed8",
    "생활안내":         "#7c3aed",
}

def _smart_linebreak(text: str) -> str:
    """PDF 추출 줄바꿈 정리: 단락 구분(\n\n)은 유지, 단일 \n은 의미적 판단."""
    text = text.replace("\n\n", "\x00")
    lines = text.split("\n")
    parts = []
    for i, ln in enumerate(lines[:-1]):
        nxt = lines[i + 1].lstrip()
        keep = (
            bool(re.match(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]", nxt))  # 원형 번호 ①② (. 없음)
            or bool(re.match(r"^\d+[.)]\s", nxt))                     # 아라비아 번호 1. 2)
            or bool(re.match(r"^제\d+조", nxt))                        # 조항 헤더
            or bool(re.match(r"^[-•○◦]\s", nxt))                      # 불릿
            or bool(re.search(r"[다요오]\s*$", ln.rstrip()))            # 문장 종결
            or ln.rstrip().endswith(".")                               # 마침표
        )
        parts.append(ln + ("<br>" if keep else " "))
    parts.append(lines[-1])
    return "".join(parts).replace("\x00", "<br><br>")


def render_article_card(art: dict, keyword: str = "", highlights: list[str] = None) -> None:
    content = art["content"]
    terms = highlights if highlights else ([keyword] if keyword else [])
    for term in terms:
        if term:
            content = re.sub(
                f"(?i)({re.escape(term)})",
                r"<mark class='hl'>\1</mark>",
                content,
            )
    lc = DOC_COLORS.get(art["doc"], "#555")
    display_title = art["title"].split(" > ")[-1] if " > " in art["title"] else art["title"]
    st.html(f"""
<style>
  body {{ margin:0; }}
  .card {{ display:flex; background:#fffdf8; border:1px solid rgba(104,82,51,0.14);
           border-radius:12px; margin-bottom:4px; overflow:hidden;
           box-shadow:0 4px 14px rgba(67,49,27,0.07); font-family:Pretendard,'Noto Sans KR',sans-serif; }}
  .inner {{ flex:1; padding:14px 18px 14px 14px; }}
  .doc-lbl {{ font-size:0.72rem; font-weight:700; }}
  .card-title {{ font-size:0.95rem; font-weight:700; color:#2d2419; margin-left:8px; }}
  .card-body {{ font-size:0.86rem; color:#574936; line-height:1.85; margin-top:9px; }}
  .hl {{ background:#fff0b8; border-radius:3px; padding:0 2px; }}
  @media (prefers-color-scheme: dark) {{
    .card {{ background:#fffdf8; border-color:rgba(104,82,51,0.14);
             box-shadow:0 4px 14px rgba(67,49,27,0.07); }}
    .card-title {{ color:#2d2419; }}
    .card-body {{ color:#574936; }}
    .hl {{ background:#fff0b8; color:#2d2419; }}
  }}
</style>
<div class='card'>
  <div style='width:5px;flex-shrink:0;background:{lc}'></div>
  <div class='inner'>
    <div>
      <span class='doc-lbl' style='color:{lc}'>{art["doc"]}</span>
      <span class='card-title'>{display_title}</span>
    </div>
    <div class='card-body'>{_smart_linebreak(content)}</div>
  </div>
</div>""")


def render_related_articles_details(articles: list[dict]) -> None:
    cards = []
    for art in articles:
        lc = DOC_COLORS.get(art["doc"], "#555")
        display_title = art["title"].split(" > ")[-1] if " > " in art["title"] else art["title"]
        cards.append(f"""
<div class='rel-card'>
  <div style='width:5px;flex-shrink:0;background:{lc}'></div>
  <div class='rel-inner'>
    <div>
      <span class='rel-doc' style='color:{lc}'>{art["doc"]}</span>
      <span class='rel-title'>{display_title}</span>
    </div>
    <div class='rel-body'>{_smart_linebreak(art["content"])}</div>
  </div>
</div>""")
    st.html(f"""
<style>
  body {{ margin:0; }}
  details.rel-details {{
    margin-top: 14px;
    border: 1px solid rgba(104,82,51,0.16);
    border-radius: 12px;
    background: #fffaf1;
    font-family: Pretendard,'Noto Sans KR',sans-serif;
    overflow: hidden;
  }}
  details.rel-details > summary {{
    cursor: pointer;
    list-style: none;
    padding: 12px 14px;
    color: #5c4933;
    font-size: 0.9rem;
    font-weight: 700;
  }}
  details.rel-details > summary::-webkit-details-marker {{ display: none; }}
  details.rel-details > summary::after {{
    content: '+';
    float: right;
    font-weight: 700;
    color: #8a7359;
  }}
  details.rel-details[open] > summary::after {{ content: '-'; }}
  .rel-content {{ padding: 0 12px 12px; }}
  .rel-card {{ display:flex; background:#fffdf8; border:1px solid rgba(104,82,51,0.14);
           border-radius:12px; margin-bottom:6px; overflow:hidden;
           box-shadow:0 4px 14px rgba(67,49,27,0.07); }}
  .rel-inner {{ flex:1; padding:14px 18px 14px 14px; }}
  .rel-doc {{ font-size:0.72rem; font-weight:700; }}
  .rel-title {{ font-size:0.95rem; font-weight:700; color:#2d2419; margin-left:8px; }}
  .rel-body {{ font-size:0.86rem; color:#574936; line-height:1.85; margin-top:9px; }}
</style>
<details class='rel-details'>
  <summary>관련 내용 원문 보기</summary>
  <div class='rel-content'>
    {''.join(cards)}
  </div>
</details>""")

# ─────────────────────────────────────────
# 10-a. 키워드 검색 실행
# ─────────────────────────────────────────
def run_keyword_search(query: str) -> tuple[list[dict], list[str]]:
    kw = query.strip()
    search_terms = [kw.lower()]
    for syn_key, syn_val in _SYNONYMS.items():
        if syn_key in kw and syn_val.lower() not in search_terms:
            search_terms.append(syn_val.lower())
    keyword_docs = [n for n in DOC_ORDER if n != "생활안내"]
    matched: list[dict] = []
    for doc_name in keyword_docs:
        arts = get_articles(doc_name, pdf_texts[doc_name])
        doc_matched = []
        for a in arts:
            tl = a["title"].lower()
            cl = a["content"].lower()
            if any(t in tl for t in search_terms):
                doc_matched.append(a)
            elif any(t in cl for t in search_terms):
                doc_matched.append(a)
        matched.extend(doc_matched[:50])
    return matched, search_terms

# ─────────────────────────────────────────
# 10-b. AI 프롬프트 빌더 + 채팅 UI 헬퍼
# ─────────────────────────────────────────
def build_prompt(doc_name: str, context: str, question: str) -> str:
    if doc_name == "생활안내":
        return (
            f"[입주 생활안내 내용]\n{context}\n\n"
            f"[질문]\n{question}\n\n"
            "위 질문에 답변하되, 반드시 다음 규칙을 따라:\n"
            "1. 헤더(#, ##) 없이 **볼드**와 목록(-)만 사용해서 친근하고 자연스러운 말투로 답변\n"
            "2. 답변 마지막에 반드시 빈 줄 하나 띄운 뒤 새 줄에 📌 로 시작하는 출처 명시 (필수):\n"
            "   예: 📌 생활안내 > 쓰레기 분리배출 요령\n"
            "3. 안내문에 없는 내용이면 '해당 안내문에서 찾을 수 없습니다'라고만 답변\n"
            "출처 없이 답변을 끝내지 마시오."
        )
    else:
        fee_block = (
            f"\n\n[주차 요금표 별표1 — 직접 데이터]\n{_PARKING_FEE_SUPPLEMENT}"
            if doc_name == "주차규약" else ""
        )
        return (
            f"[규약 전문]\n{context}{fee_block}\n\n"
            f"[질문]\n{question}\n\n"
            "위 질문에 답변하되, 반드시 다음 규칙을 따라:\n"
            "1. 헤더(#, ##) 없이 **볼드**와 목록(-)만 사용해서 친근하고 자연스러운 말투로 답변\n"
            "2. 답변 마지막에 반드시 빈 줄 하나 띄운 뒤 새 줄에 📌 로 시작하는 근거 명시 (필수):\n"
            "   - 조항인 경우: 📌 관리규약 제N조 또는 📌 주차규약 제N조 또는 📌 커뮤니티센터 규약 제N조\n"
            "   - 별표인 경우: 📌 주차규약 별표 N\n"
            "   - 첨부인 경우: 📌 커뮤니티센터 규약 첨부 #N\n"
            "3. 규약 이름은 반드시 '관리규약', '주차규약', '커뮤니티센터 규약' 중 하나만 사용\n"
            "4. 근거 뒤에 항목번호(가., ①, ② 등)는 붙이지 마시오\n"
            "5. 주차 요금 질문 시 [주차 요금표 별표1] 데이터를 반드시 활용하여 구체적인 금액을 계산해 답변\n"
            "6. 규약에 없으면 '해당 규약에서 찾을 수 없습니다'라고만 답변\n"
            "근거 없이 답변을 끝내지 마시오."
        )

def _scroll_to_anchor(anchor_id: str) -> None:
    components.html(
        f"""
        <script>
        setTimeout(() => {{
          const el = window.parent.document.getElementById("{anchor_id}");
          if (el) el.scrollIntoView({{ behavior: "smooth", block: "start" }});
        }}, 220);
        </script>
        """,
        height=0,
    )


def _user_bubble(text: str, anchor_id: str = "") -> None:
    anchor_attr = f' id="{anchor_id}"' if anchor_id else ""
    st.markdown(
        f'<div{anchor_attr} style="display:flex;justify-content:flex-end;margin:4px 0 8px 0;scroll-margin-top:18px">'
        f'<div style="background:#4f68e8;color:#fff;border-radius:16px 16px 4px 16px;'
        f'padding:10px 16px;max-width:78%;font-size:0.87rem;line-height:1.6;'
        f'word-break:break-word;font-family:\'Noto Sans KR\',sans-serif">{text}</div></div>',
        unsafe_allow_html=True,
    )

def _render_assistant_message(m: dict) -> None:
    if m.get("error"):
        st.error(m["text"])
        return
    body, cites = split_body_and_citations(m["text"])
    st.markdown("\n".join(body).rstrip())
    if cites:
        st.markdown("")
        st.markdown("\n".join(cites))
    if m.get("articles"):
        render_related_articles_details(m["articles"])

# ─────────────────────────────────────────
# 11. 홈 화면 vs 대화 화면
# ─────────────────────────────────────────
_mode     = st.session_state.search_mode
_selected = st.session_state.selected_doc
_in_chat  = st.session_state.get("in_chat", False)

if not _in_chat:
    st.markdown(
        "<div class='sky-home'>"
        "<p class='sky-hello'>입주민님, 안녕하세요</p>"
        "<p class='sky-question'>무엇을 도와드릴까요?</p>"
        "<p class='sky-guide'>아래 버튼을 눌러 규약을 검색할 수 있습니다.</p>"
        "</div>",
        unsafe_allow_html=True,
    )

else:
    # ── 대화 화면 ──
    if _mode == "keyword":
        _kw_results = st.session_state.get("keyword_results", [])
        _kw_query   = st.session_state.get("keyword_query", "")
        _kw_terms   = st.session_state.get("keyword_terms", [])
        if _kw_results:
            st.markdown("<div id='sky-search-result' style='scroll-margin-top:18px'></div>", unsafe_allow_html=True)
            if st.session_state.pop("scroll_to_search_result", False):
                _scroll_to_anchor("sky-search-result")
            st.markdown(
                f"<div class='sky-result-summary'><b>{_kw_query}</b> 검색 결과 "
                f"<b>{len(_kw_results)}개</b> 조항을 찾았습니다.</div>",
                unsafe_allow_html=True,
            )
            for _art in _kw_results:
                render_article_card(_art, highlights=_kw_terms)
        else:
            st.markdown("<div class='sky-empty'>검색 결과가 없습니다. 다른 키워드로 검색해 보세요.</div>", unsafe_allow_html=True)

    else:
        # AI 대화
        if "messages_by_doc" not in st.session_state:
            st.session_state.messages_by_doc = {}
        if _selected not in st.session_state.messages_by_doc:
            st.session_state.messages_by_doc[_selected] = []
        _msgs: list[dict] = st.session_state.messages_by_doc[_selected]

        if _msgs:
            _pairs = [
                (_msgs[i], _msgs[i + 1])
                for i in range(0, len(_msgs) - 1, 2)
                if i + 1 < len(_msgs)
            ]
            for _user_m, _asst_m in reversed(_pairs):
                _user_bubble(_user_m["text"])
                with st.chat_message("assistant"):
                    _render_assistant_message(_asst_m)
        else:
            st.markdown(
                f"<div style='text-align:center;color:#aaa;padding:2.5rem 0'>"
                f"<div style='font-size:2rem;margin-bottom:0.5rem'>💬</div>"
                f"<div style='font-size:0.9rem'><b>{_selected}</b>에 대해 질문하세요</div></div>",
                unsafe_allow_html=True,
            )

# ─────────────────────────────────────────
# 12. 하단 입력 영역
# ─────────────────────────────────────────
_mode     = st.session_state.search_mode
_selected = st.session_state.selected_doc

_BADGE_TO_TARGET = {
    "키워드": ("keyword", None),
    "주차": ("ai", "주차규약"),
    "커뮤니티": ("ai", "커뮤니티센터 규약"),
    "관리": ("ai", "관리규약"),
    "생활": ("ai", "생활안내"),
}
_TARGET_TO_BADGE = {
    ("keyword", None): "키워드",
    ("ai", "주차규약"): "주차",
    ("ai", "커뮤니티센터 규약"): "커뮤니티",
    ("ai", "관리규약"): "관리",
    ("ai", "생활안내"): "생활",
}
_badge_options = [
    _badge for _badge, (_bmode, _bdoc) in _BADGE_TO_TARGET.items()
    if _bdoc is None or _bdoc in DOC_ORDER
]
_current_badge = _TARGET_TO_BADGE.get(
    ("keyword", None) if _mode == "keyword" else ("ai", _selected),
    "키워드",
)
if _current_badge not in _badge_options:
    _current_badge = "키워드"

with st.container(key="sky_mode_bar"):
    _next_badge = st.pills(
        "검색 범위",
        _badge_options,
        default=_current_badge,
        label_visibility="collapsed",
        key="sky_selected_badge",
    )

if _next_badge and _next_badge != _current_badge:
    _next_mode, _next_doc = _BADGE_TO_TARGET[_next_badge]
    st.session_state.search_mode = _next_mode
    if _next_doc:
        st.session_state.selected_doc = _next_doc
        _has_ai_history = bool(st.session_state.get("messages_by_doc", {}).get(_next_doc))
        st.session_state.in_chat = _has_ai_history
    else:
        st.session_state.in_chat = bool(st.session_state.get("keyword_query"))
    st.rerun()

_mode     = st.session_state.search_mode
_selected = st.session_state.selected_doc

# 통합 입력창
_PLACEHOLDERS = {
    "주차규약":         "방문차량 무료 주차는 몇 시간까지야?",
    "커뮤니티센터 규약": "헬스장 이용시간이 어떻게 돼?",
    "관리규약":         "동대표 자격요건이 뭐야?",
    "생활안내":         "쓰레기 분리수거는 어떻게 해?",
}
_ph = "키워드 입력 (주차, 헬스장, 키즈카페 등)" if _mode == "keyword" else _PLACEHOLDERS.get(_selected, "질문을 입력하세요")

if _prompt := st.chat_input(_ph):
    st.session_state.in_chat = True

    if _mode == "keyword":
        _results, _terms = run_keyword_search(_prompt)
        st.session_state.keyword_results = _results
        st.session_state.keyword_query   = _prompt
        st.session_state.keyword_terms   = _terms
        st.session_state.scroll_to_search_result = True
        st.rerun()

    else:
        if not api_ready:
            st.error("API 키가 설정되지 않아 AI 검색을 사용할 수 없습니다.")
            st.stop()

        if "messages_by_doc" not in st.session_state:
            st.session_state.messages_by_doc = {}
        if _selected not in st.session_state.messages_by_doc:
            st.session_state.messages_by_doc[_selected] = []
        _msgs = st.session_state.messages_by_doc[_selected]

        _user_bubble(_prompt, anchor_id="sky-current-question")
        _scroll_to_anchor("sky-current-question")
        _response_text = None
        _related: list[dict] = []
        _last_err = ""

        _asst_container = st.container()
        _hist_container = st.container()

        _old_pairs = [
            (_msgs[i], _msgs[i + 1])
            for i in range(0, len(_msgs) - 1, 2)
            if i + 1 < len(_msgs)
        ]
        with _hist_container:
            for _um, _am in reversed(_old_pairs):
                _user_bubble(_um["text"])
                with st.chat_message("assistant"):
                    _render_assistant_message(_am)

        with _asst_container:
            with st.chat_message("assistant"):
                _ph_el = st.empty()
                _ph_el.markdown("_답변을 생성하는 중입니다..._")
                try:
                    _all_arts = get_articles(_selected, pdf_texts[_selected])
                    _context  = get_context_for_ai(_selected, _prompt, _all_arts)
                    _full_p   = build_prompt(_selected, _context, _prompt)
                    _cache_key = (_selected, _prompt.strip())
                    _entry = _RESPONSE_CACHE.get(_cache_key)
                    _cached = _entry[0] if (_entry and time.time() - _entry[1] < _CACHE_TTL) else None

                    if _cached is not None:
                        _response_text = _cached
                    else:
                        _accumulated = ""
                        for _chunk in ai_generate_smart_stream(_full_p):
                            _accumulated += _chunk
                            _ph_el.markdown(_accumulated + " ▌")
                        if not _accumulated.strip():
                            raise RuntimeError("빈 응답")
                        _response_text = re.sub(r"([^\n])\n*(📌)", r"\1\n\n\2", _accumulated)
                        _response_text = _collapse_citations(_response_text)
                        _RESPONSE_CACHE[_cache_key] = (_response_text, time.time())

                    _body, _cites = split_body_and_citations(_response_text)
                    _final = "\n".join(_body).rstrip()
                    if _cites:
                        _final += "\n\n" + "\n".join(_cites)
                    _ph_el.markdown(_final)

                    _related = [] if _selected == "생활안내" else find_related_articles(
                        _response_text, _all_arts, _selected
                    )
                except Exception as _e:
                    _last_err = friendly_error_message(_e)
                    _ph_el.markdown(_last_err)

        if _response_text:
            _msgs.append({"role": "user", "text": _prompt})
            _msgs.append({"role": "assistant", "text": _response_text, "articles": _related})
        elif _last_err:
            _msgs.append({"role": "user", "text": _prompt})
            _msgs.append({"role": "assistant", "text": _last_err, "articles": [], "error": True})

        st.rerun()
