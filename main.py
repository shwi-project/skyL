 from typing import Iterator
 
 # 모듈 수준 공유 캐시 (모든 사용자 세션이 공유, TTL 1시간)
 _RESPONSE_CACHE: dict[tuple, tuple[str, float]] = {}
 _CACHE_TTL = 3600
 
 import pdfplumber
 import requests
 import streamlit as st
 
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
-    max-width: 760px !important;
+    max-width: 780px !important;
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
+    justify-content: flex-start !important;
 }
 
 /* ── secondary 버튼 = Gemini 제안 칩 ── */
 [data-testid="stBaseButton-secondary"],
 [data-testid="baseButton-secondary"],
 [data-testid="stButton"] button[kind="secondary"] {
-    background: #e8edf8 !important;
+    background: #e9eef6 !important;
     border: none !important;
     color: #1f2937 !important;
-    padding: 0.6rem 1.3rem !important;
+    padding: 0.62rem 1.05rem !important;
     box-shadow: none !important;
+    border-radius: 999px !important;
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
-    background: #1a73e8 !important;
+    background: #d3e3fd !important;
     border: none !important;
-    color: white !important;
-    padding: 0.6rem 1.3rem !important;
+    color: #174ea6 !important;
+    padding: 0.62rem 1.05rem !important;
     box-shadow: none !important;
+    border-radius: 999px !important;
 }
 [data-testid="stBaseButton-primary"]:hover,
 [data-testid="baseButton-primary"]:hover {
-    background: #1558b0 !important;
+    background: #c5dafc !important;
 }
 [data-testid="stBaseButton-primary"] p,
 [data-testid="baseButton-primary"] p,
 [data-testid="stBaseButton-primary"] span,
 [data-testid="baseButton-primary"] span {
-    color: white !important;
+    color: #174ea6 !important;
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
-    padding: 0 0 12px !important;
+    padding: 0 0 10px !important;
 }
 [data-testid="stChatInput"] > div,
 [data-testid="stChatInputContainer"] {
-    border-radius: 26px !important;
-    border: 1px solid #c8cdd8 !important;
+    border-radius: 24px !important;
+    border: 1px solid #d0d7e2 !important;
     background: #ffffff !important;
-    box-shadow: 0 2px 12px rgba(0,0,0,0.07) !important;
-    padding: 10px 16px !important;
+    box-shadow: 0 1px 4px rgba(60,64,67,0.3), 0 4px 14px rgba(60,64,67,0.15) !important;
+    padding: 11px 16px !important;
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
-    color: #9aa0b0 !important;
+    color: #80868b !important;
 }
 
+.gemini-topbar {
+    display:flex;align-items:center;justify-content:space-between;
+    padding:10px 2px 8px 2px;
+}
+.gemini-brand {
+    display:flex;align-items:center;gap:10px;color:#3c4043;
+    font-size:1.2rem;font-weight:500;letter-spacing:-0.2px;
+}
+.gemini-menu { color:#5f6368;font-size:1rem;padding:4px 6px;border-radius:999px; }
+.gemini-right { display:flex;align-items:center;gap:8px; }
+
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
 
 # ── 헤더: 순수 HTML로 렌더 (Gemini 스타일 nav) ──
 try:
     with open("logo.png", "rb") as f:
         _logo_b64 = base64.b64encode(f.read()).decode()
     _logo_sm = (
         f"<img src='data:image/png;base64,{_logo_b64}' "
         "style='width:28px;height:28px;object-fit:contain;vertical-align:middle;'>"
     )
 except Exception:
     _logo_sm = "<span style='font-size:1.3rem;vertical-align:middle'>🏰</span>"
 
 _in_chat_now = st.session_state.get("in_chat", False)
 
 _hcol_title, _hcol_btn = st.columns([8, 2])
 with _hcol_title:
     st.markdown(
-        f"<div style='display:flex;align-items:center;gap:10px;padding:10px 0 6px'>"
-        f"{_logo_sm}"
-        f"<span style='font-size:1.1rem;font-weight:700;color:#1a1a2e;letter-spacing:-0.3px;'"
-        f">원당역 롯데캐슬스카이엘</span></div>",
+        f"<div class='gemini-topbar'>"
+        f"<div class='gemini-brand'><span class='gemini-menu'>☰</span><span>Gemini</span></div>"
+        f"<div class='gemini-right'>{_logo_sm}</div>"
+        f"</div>",
         unsafe_allow_html=True,
     )
 with _hcol_btn:
     if _in_chat_now:
         if st.button("← 홈으로", key="home_btn", type="secondary"):
             for _k in ["in_chat", "keyword_results", "keyword_query", "keyword_terms", "messages_by_doc"]:
                 st.session_state.pop(_k, None)
             st.session_state.search_mode = "ai"
             st.rerun()
 
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
@@ -1045,56 +1059,56 @@ def _user_bubble(text: str) -> None:
 
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
         with st.expander("📋 관련 내용 원문 보기", expanded=False):
             for art in m["articles"]:
                 render_article_card(art)
 
 # ─────────────────────────────────────────
 # 11. 홈 화면 vs 대화 화면
 # ─────────────────────────────────────────
 _mode     = st.session_state.search_mode
 _selected = st.session_state.selected_doc
 _in_chat  = st.session_state.get("in_chat", False)
 
 if not _in_chat:
     # ── 홈 화면: Gemini 스타일 좌측 인사말 + 세로 칩 ──
     st.markdown(
-        "<div style='padding:2.2rem 0 1.8rem'>"
-        "<p style='font-size:0.95rem;color:#5f6b7a;margin:0 0 0.4rem;font-weight:400'>"
+        "<div style='padding:2.7rem 0 1.8rem'>"
+        "<p style='font-size:0.95rem;color:#5f6368;margin:0 0 0.45rem;font-weight:400'>"
         "입주민님, 안녕하세요</p>"
-        "<p style='font-size:1.85rem;font-weight:700;color:#1a1a2e;line-height:1.3;"
-        "letter-spacing:-0.5px;margin:0'>"
-        "규약 검색, AI 질문으로<br>무엇이든 도와드리겠습니다.</p>"
+        "<p style='font-size:2.8rem;font-weight:500;color:#202124;line-height:1.14;"
+        "letter-spacing:-1.1px;margin:0'>"
+        "계획, 학습, 아이디어 실현<br>등 다양한 작업을 도와드리겠습니다.</p>"
         "</div>",
         unsafe_allow_html=True,
     )
 
     # 칩 목록 (Gemini 스타일: 세로 단일 컬럼, 좌측 정렬, 아이콘 포함)
     _chips = [
         ("🔎  키워드 통합검색",   "chip_kw",           "keyword", None),
         ("🚗  주차 규약",         "chip_주차규약",      "ai",      "주차규약"),
         ("🏢  커뮤니티센터 규약", "chip_커뮤니티센터 규약", "ai", "커뮤니티센터 규약"),
         ("📋  관리 규약",         "chip_관리규약",      "ai",      "관리규약"),
         ("📌  생활안내",          "chip_생활안내",      "ai",      "생활안내"),
     ]
     _chip_col, _ = st.columns([0.62, 0.38])
     with _chip_col:
         for _label, _key, _cmode, _cdoc in _chips:
             if _cdoc and _cdoc not in DOC_ORDER:
                 continue
             _is_active = (
                 (_cmode == "keyword" and _mode == "keyword")
                 if _cdoc is None
                 else (_mode == "ai" and _selected == _cdoc)
             )
             if st.button(
                 _label,
                 key=_key,
 
EOF
)
