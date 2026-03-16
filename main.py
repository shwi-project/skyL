import base64
import os
import re
import time

import pdfplumber
import requests
import streamlit as st

# ─────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────
st.set_page_config(page_title="롯데캐슬스카이엘 규약 검색", page_icon="🏰", layout="wide", menu_items={})

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600&display=swap');

/* 텍스트 영역에만 폰트 적용 — 아이콘/이모지 제외 */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatInput"] textarea,
[data-testid="stTextInput"] input {
    font-family: 'Noto Sans KR', sans-serif !important;
}

/* 규약 선택 버튼 텍스트 크기 */
[data-testid="stButton"] button p {
    font-size: 0.82rem !important;
}

/* 아바타 크기 축소 */
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    width: 24px !important;
    height: 24px !important;
    min-width: 24px !important;
}

/* 채팅 메시지 패딩 최소화 */
[data-testid="stChatMessage"] {
    padding: 0.5rem !important;
    gap: 0.4rem !important;
}
/* assistant 아바타만 숨기기 */
[data-testid="stChatMessageAvatarAssistant"] {
    display: none !important;
}
/* user 아바타 크기 유지 */
[data-testid="stChatMessageAvatarUser"] {
    width: 24px !important;
    height: 24px !important;
    min-width: 24px !important;
}

/* AI 채팅 메시지 텍스트 크기 및 간격 */
[data-testid="stChatMessageAvatarAssistant"] ~ div p {
    font-size: 0.85rem !important;
    line-height: 1.7 !important;
    margin-bottom: 0.4rem !important;
}
[data-testid="stChatMessage"] li {
    font-size: 0.85rem !important;
    margin-bottom: 0.3rem !important;
    line-height: 1.7 !important;
}
[data-testid="stChatMessage"] ul,
[data-testid="stChatMessage"] ol {
    margin-top: 0.4rem !important;
    margin-bottom: 0.4rem !important;
}

/* Streamlit 푸터 배지 숨기기 */
[class*="profilePreview"] { display: none !important; }
[class*="_link_gzau3"] { display: none !important; }
[class*="viewerBadge"] { display: none !important; }

/* 타이틀 아래 여백 축소 */
.main .block-container { padding-top: 0 !important; }
[data-testid="stMainBlockContainer"] {
    padding-top: 3rem !important;
}
.st-emotion-cache-zy6yx3 {
    padding-top: 3rem !important;
}
hr { margin-top: 0.3rem !important; margin-bottom: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)

# 헤더
try:
    with open("logo.png", "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()
    logo_html = (
        f"<img src='data:image/png;base64,{logo_b64}' "
        "style='width:36px;height:36px;object-fit:contain;"
        "vertical-align:top;margin-right:10px;pointer-events:none;'>"
    )
except Exception:
    logo_html = "<span style='font-size:1.4rem;vertical-align:top;margin-right:8px'>🏰</span>"

st.markdown(
    f"""<div style='display:flex;align-items:flex-start;margin-bottom:2px'>
    {logo_html}
    <div style='line-height:1.2'>
      <div style='font-size:1.1rem;font-weight:700'>롯데캐슬스카이엘 규약 통합 검색</div>
      <div style='font-size:0.78rem;color:#999;margin-top:2px'>우리아파트 규약을 키워드 및 AI로 검색합니다.</div>
    </div></div>""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# ⚙️ 컨텍스트 압축 설정
# True  → 관리규약 질문 시 관련 조항만 추려서 전송 (토큰 절약)
# False → 기존 방식대로 규약 전문 전체 전송 (원복)
# ─────────────────────────────────────────
USE_CONTEXT_COMPRESSION = True

# 압축 시 최대 조항 수 (많을수록 품질↑, 토큰↑)
MAX_ARTICLES_IN_CONTEXT = 40

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

PDF_FILES = {
    "관리규약":         "rules_management.pdf",
    "주차규약":         "rules_parking.pdf",
    "커뮤니티센터 규약": "rules_community.pdf",
}

# 압축 적용 대상 규약 (전문이 긴 규약만)
COMPRESSION_TARGET_DOCS = {"관리규약"}

pdf_texts: dict[str, str] = {}
for name, path in PDF_FILES.items():
    t = load_pdf_text(path)
    if t:
        pdf_texts[name] = t

if not pdf_texts:
    st.error("📂 GitHub 저장소에 PDF 파일을 업로드해주세요.")
    st.stop()

loaded_names = list(pdf_texts.keys())

# ─────────────────────────────────────────
# 3. 검색 대상 선택
# ─────────────────────────────────────────
st.divider()
DOC_ORDER = [n for n in ["주차규약", "커뮤니티센터 규약", "관리규약"] if n in pdf_texts]

if "selected_doc" not in st.session_state or st.session_state.selected_doc not in DOC_ORDER:
    st.session_state.selected_doc = DOC_ORDER[0]

cols = st.columns(len(DOC_ORDER))
for i, doc in enumerate(DOC_ORDER):
    with cols[i]:
        is_active = st.session_state.selected_doc == doc
        if st.button(
            doc,
            key=f"doc_btn_{doc}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.selected_doc = doc
            st.session_state["_keyword_clear"] = True
            st.rerun()

selected = st.session_state.selected_doc
selected_names = [selected]
combined_text = f"=== [{selected}] ===\n{pdf_texts[selected]}"

# ─────────────────────────────────────────
# 4. Gemini AI
# ─────────────────────────────────────────
def ai_generate(prompt: str) -> str:
    api_key = st.session_state.get("GOOGLE_API_KEY", "")
    model   = "gemini-2.5-flash"
    url     = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 8192},
    }
    last_err = ""
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=120)
        if resp.status_code == 429:
            last_err = resp.text
            time.sleep((attempt + 1) * 15)
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
                "generationConfig": {"maxOutputTokens": 8192},
            }, timeout=120)
            if cont.ok:
                text += cont.json()["candidates"][0]["content"]["parts"][0]["text"]
        return text
    raise RuntimeError(f"429 한도 초과: {last_err}")

# ─────────────────────────────────────────
# 5. 조항 파싱
# ─────────────────────────────────────────
ARTICLE_RE = re.compile(
    r"(제\s*\d+\s*조[^\n]*(?:\n(?!제\s*\d+\s*조).+)*)",
    re.MULTILINE
)
TITLE_RE = re.compile(
    r"제\s*(\d+)\s*조(?:의\s*\d+)?"
    r"(?:\s*【([^】]*)】|\s*\(([^\)]{1,20})\)|\s+([가-힣a-zA-Z\s·,]{2,20}?))?"
)

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
        if len(lines) <= 1:
            continue
        title = extract_title(lines[0])
        if len(block) > 1500:
            block = block[:1500].strip() + "...(이하 생략)"
        articles.append({"doc": doc_name, "title": title, "content": block})
    return articles

def parse_attachments(doc_name: str, text: str) -> list[dict]:
    results = []
    pat = re.compile(
        r"((?:(?:▣\s*)?첨부\s*#\d+|<별표\s*\d+>)[^\n]*(?:\n(?!(?:(?:▣\s*)?첨부\s*#\d+|<별표\s*\d+>)).+)*)",
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

@st.cache_data(show_spinner=False)
def get_articles(doc_name: str, text: str, _v: int = 1) -> list[dict]:
    arts = parse_articles(doc_name, text)
    arts += parse_attachments(doc_name, text)
    return arts

# ─────────────────────────────────────────
# 5-1. 컨텍스트 압축 — 질문 관련 조항 추출
# ─────────────────────────────────────────
# 한국어 불용어 (검색 의미 없는 단어)
_STOPWORDS = {
    "은", "는", "이", "가", "을", "를", "의", "에", "서", "도", "만",
    "로", "으로", "와", "과", "한", "하다", "있다", "없다", "되다",
    "하면", "되면", "인지", "어떤", "어떻게", "무엇", "언제", "어디",
    "뭐야", "뭐", "인가", "나요", "까요", "예요", "이에요", "있나요",
    "있어요", "없나요", "알려줘", "알려주세요", "궁금해", "궁금합니다",
}

def extract_keywords(question: str) -> list[str]:
    """질문에서 의미 있는 키워드 추출 (2글자 이상 명사/복합어 위주)"""
    # 특수문자 제거 후 2글자 이상 단어 추출
    words = re.findall(r"[가-힣a-zA-Z0-9]{2,}", question)
    keywords = [w for w in words if w not in _STOPWORDS]
    return keywords

def score_article(art: dict, keywords: list[str]) -> int:
    """조항과 키워드 간 매칭 점수 계산"""
    score = 0
    title_lower = art["title"].lower()
    content_lower = art["content"].lower()
    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in title_lower:
            score += 3   # 제목 매칭은 가중치 높게
        elif kw_lower in content_lower:
            score += 1
    return score

def build_compressed_context(doc_name: str, question: str, all_arts: list[dict]) -> str:
    """
    관리규약 대상으로 질문과 관련된 조항만 추려서 컨텍스트 생성.
    관련 조항이 없으면 전체 전문 반환 (fallback).
    """
    keywords = extract_keywords(question)
    if not keywords:
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    # 점수 계산
    scored = []
    for art in all_arts:
        if art["doc"] != doc_name:
            continue
        s = score_article(art, keywords)
        if s > 0:
            scored.append((s, art))

    # 점수 높은 순 정렬, 최대 MAX_ARTICLES_IN_CONTEXT개
    scored.sort(key=lambda x: x[0], reverse=True)
    top_arts = [art for _, art in scored[:MAX_ARTICLES_IN_CONTEXT]]

    if not top_arts:
        # 관련 조항 없으면 전체 전문 fallback
        return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

    # 원래 조항 순서대로 재정렬 (번호 순)
    def art_sort_key(a):
        m = re.search(r"제\s*(\d+)\s*조", a["title"])
        return int(m.group(1)) if m else 9999

    top_arts.sort(key=art_sort_key)

    ctx_parts = [f"=== [{doc_name}] (관련 조항 {len(top_arts)}개) ==="]
    for art in top_arts:
        ctx_parts.append(art["content"])

    return "\n\n".join(ctx_parts)

def get_context_for_ai(doc_name: str, question: str, all_arts: list[dict]) -> str:
    """
    USE_CONTEXT_COMPRESSION 플래그와 대상 규약에 따라
    전체 전문 또는 압축 컨텍스트 반환
    """
    if USE_CONTEXT_COMPRESSION and doc_name in COMPRESSION_TARGET_DOCS:
        return build_compressed_context(doc_name, question, all_arts)
    return f"=== [{doc_name}] ===\n{pdf_texts[doc_name]}"

# ─────────────────────────────────────────
# 6. 근거 조항 추출 (AI 응답 → 규약명+조번호)
# ─────────────────────────────────────────
DOC_PAT = re.compile(
    r"(관리규약"
    r"|주차\s*관리\s*규정?"
    r"|주차\s*규약"
    r"|커뮤니티\s*센터?\s*규약"
    r"|주민공동시설\s*운영규정?"
    r"|운영규정)"
)

def classify_doc(raw: str) -> str:
    if "관리규약" in raw and "주차" not in raw:
        return "관리규약"
    if "주차" in raw:
        return "주차규약"
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

def find_related_articles(response_text: str, all_arts: list[dict]) -> list[dict]:
    related   = []
    seen_keys = set()

    anchor_text = " ".join(re.findall(r"📌\s*([^\n]+)", response_text))
    search_text = anchor_text if anchor_text else response_text

    for doc_name, num in extract_pairs(search_text):
        key = (doc_name, num)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        pat = re.compile(rf"제\s*{num}\s*조")
        for art in all_arts:
            if art["doc"] == doc_name and pat.search(art["title"]):
                related.append(art)
                break

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
        doc_name = classify_doc(raw_doc) if raw_doc else None
        for art in all_arts:
            if doc_name and art["doc"] != doc_name:
                continue
            if re.search(rf"별표\s*{num}", art["title"]) and len(art["title"]) > 10 and art not in related:
                related.append(art)
                break

    return related

# ─────────────────────────────────────────
# 7. 카드 렌더링
# ─────────────────────────────────────────
DOC_COLORS = {
    "관리규약":         "#1a6ebd",
    "주차규약":         "#2e8b57",
    "커뮤니티센터 규약": "#8b4513",
}

def render_article_card(art: dict, keyword: str = "") -> None:
    content = art["content"]
    if keyword:
        content = re.sub(
            f"(?i)({re.escape(keyword)})",
            r"<mark style='background:#fff3cd;padding:0 2px;border-radius:3px'>\1</mark>",
            content,
        )
    bc = DOC_COLORS.get(art["doc"], "#555")
    st.html(f"""
<div style='border:1px solid #e0e0e0;border-radius:10px;padding:16px 20px;
            margin-bottom:12px;background:#fafafa;box-shadow:0 1px 4px rgba(0,0,0,0.06)'>
  <div style='margin-bottom:8px'>
    <span style='background:{bc};color:white;padding:2px 8px;
                 border-radius:4px;font-size:0.75rem;font-weight:600'>{art["doc"]}</span>
    &nbsp;<span style='font-size:1rem;font-weight:700;color:#222'>{art["title"]}</span>
  </div>
  <div style='font-size:0.88rem;color:#333;line-height:1.8'>{content.replace(chr(10), '<br>')}</div>
</div>""")

# ─────────────────────────────────────────
# 8. 탭 구성
# ─────────────────────────────────────────
tab_keyword, tab_ai = st.tabs(["🔎 키워드 검색", "✦ AI 질문 검색"])

# ══════════════════════════════════════════
# TAB A — 키워드 검색
# ══════════════════════════════════════════
with tab_keyword:
    if st.session_state.pop("_keyword_clear", False):
        st.session_state["keyword_input"] = ""
    keyword = st.text_input(
        "검색어", placeholder="예: 층간소음, 주차 위반, 이용 시간",
        label_visibility="collapsed", key="keyword_input",
    )

    if keyword:
        kw = keyword.lower()
        matched: list[dict] = []
        for doc_name in selected_names:
            arts = get_articles(doc_name, pdf_texts[doc_name])
            matched.extend(a for a in arts if kw in a["title"].lower())
            matched.extend(a for a in arts if kw in a["content"].lower() and kw not in a["title"].lower())
        matched = matched[:10]

        if not matched:
            st.warning(f"**'{keyword}'** 에 해당하는 조항을 찾지 못했습니다.")
        else:
            st.success(f"총 **{len(matched)}개** 조항 발견")

            st.divider()
            for art in matched:
                render_article_card(art, keyword)

# ══════════════════════════════════════════
# TAB B — AI 질문 검색
# ══════════════════════════════════════════
with tab_ai:
    if not api_ready:
        st.error("API 키가 설정되지 않아 AI 검색을 사용할 수 없습니다.")
        st.stop()

    for k in ("ai_question", "ai_response", "ai_articles"):
        if k not in st.session_state:
            st.session_state[k] = None if k != "ai_articles" else []

    if prompt := st.chat_input("질문을 입력하세요  (예: 방문차량 무료 주차는 몇 시간까지야?)"):
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("AI가 답변을 생성하는 중..."):
                try:
                    # 조항 파싱 (압축용)
                    all_arts = []
                    for dn in selected_names:
                        all_arts += get_articles(dn, pdf_texts[dn])

                    # 컨텍스트 결정 (압축 or 전체)
                    context = get_context_for_ai(selected, prompt, all_arts)

                    response_text = ai_generate(
                        f"[규약 전문]\n{context}\n\n"
                        f"[질문]\n{prompt}\n\n"
                        "위 질문에 답변하되, 반드시 다음 규칙을 따라:\n"
                        "1. 헤더(#, ##) 없이 **볼드**와 목록(-)만 사용해서 친근하고 자연스러운 말투로 답변\n"
                        "2. 답변 마지막에 반드시 빈 줄 하나 띄운 뒤 새 줄에 📌 로 시작하는 근거 명시 (필수):\n"
                        "   - 조항인 경우: 📌 관리규약 제N조 또는 📌 주차규약 제N조 또는 📌 커뮤니티센터 규약 제N조\n"
                        "   - 별표인 경우: 📌 주차규약 별표 N\n"
                        "   - 첨부인 경우: 📌 커뮤니티센터 규약 첨부 #N\n"
                        "3. 규약 이름은 반드시 '관리규약', '주차규약', '커뮤니티센터 규약' 중 하나만 사용\n"
                        "4. 근거 뒤에 항목번호(가., ①, ② 등)는 붙이지 마시오\n"
                        "5. 규약에 없으면 '해당 규약에서 찾을 수 없습니다'라고만 답변\n"
                        "근거 없이 답변을 끝내지 마시오."
                    )
                    response_text = re.sub(r"([^\n])\n*(📌)", r"\1\n\n\2", response_text)

                    st.markdown(response_text)

                    related = find_related_articles(response_text, all_arts)
                    if related:
                        with st.expander("📋 관련 조항 원문 보기", expanded=False):
                            for art in related:
                                render_article_card(art)

                    st.session_state.ai_question = prompt
                    st.session_state.ai_response = response_text
                    st.session_state.ai_articles = related

                except Exception as e:
                    st.error(f"❌ 오류 발생: {e}")

    elif st.session_state.ai_question:
        with st.chat_message("user"):
            st.markdown(st.session_state.ai_question)
        with st.chat_message("assistant"):
            st.markdown(st.session_state.ai_response)
            if st.session_state.ai_articles:
                with st.expander("📋 관련 조항 원문 보기", expanded=False):
                    for art in st.session_state.ai_articles:
                        render_article_card(art)
