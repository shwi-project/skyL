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
st.set_page_config(page_title="롯데캐슬스카이엘 규약 검색", page_icon="🏰", layout="wide")

# 헤더: 로고 + 타이틀
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
    f"""<div style='display:flex;align-items:flex-start;margin-bottom:4px'>
    {logo_html}
    <div style='line-height:1.2'>
      <div style='font-size:1.1rem;font-weight:700'>롯데캐슬스카이엘 규약 통합 검색</div>
      <div style='font-size:0.78rem;color:#999;margin-top:2px'>관리규약 · 주차규약 · 커뮤니티센터 규약을 키워드 및 AI로 검색합니다.</div>
    </div></div>""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# 1. API 키 설정
# ─────────────────────────────────────────
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    st.session_state["GOOGLE_API_KEY"] = API_KEY
    api_ready = True
except Exception:
    st.warning("⚠️ Streamlit Cloud의 Settings > Secrets에 GOOGLE_API_KEY를 등록해주세요.")
    api_ready = False

# ─────────────────────────────────────────
# 2. PDF 로드 (pdfplumber)
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
    "관리규약":          "rules_management.pdf",
    "주차규약":          "rules_parking.pdf",
    "커뮤니티센터 규약":  "rules_community.pdf",
}

pdf_texts: dict[str, str] = {}
for name, path in PDF_FILES.items():
    t = load_pdf_text(path)
    if t:
        pdf_texts[name] = t

if not pdf_texts:
    st.error(
        "📂 GitHub 저장소 최상위 경로에 PDF 파일을 업로드해주세요:\n\n"
        "- `rules_management.pdf`\n- `rules_parking.pdf`\n- `rules_community.pdf`"
    )
    st.stop()

loaded_names = list(pdf_texts.keys())
st.success(f"✅ 로드된 규약: {', '.join(loaded_names)}")

# ─────────────────────────────────────────
# 3. 검색 대상 선택
# ─────────────────────────────────────────
st.divider()
selected = st.multiselect(
    "🔍 검색할 규약 선택",
    options=loaded_names,
    default=loaded_names,
)
if not selected:
    st.info("검색할 규약을 하나 이상 선택해주세요.")
    st.stop()

combined_text = "\n\n".join(f"=== [{n}] ===\n{pdf_texts[n]}" for n in selected)

# ─────────────────────────────────────────
# 4. Gemini AI 호출
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
        text      = candidate["content"]["parts"][0]["text"]
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
# 세 규약 모두 "제N조"로 시작 → 다음 "제N조" 전까지를 하나의 블록으로
ARTICLE_RE = re.compile(
    r"(제\s*\d+\s*조[^\n]*(?:\n(?!제\s*\d+\s*조).+)*)",
    re.MULTILINE
)

# 제목 추출: 규약별 형식에 맞게
# 관리규약: 제N조【제목】  /  주차규약: 제N조 (제목)  /  커뮤니티: 제N조 제목(한 단어)
TITLE_RE = re.compile(
    r"제\s*(\d+)\s*조(?:의\s*\d+)?"
    r"(?:\s*【([^】]*)】"      # 【제목】
    r"|\s*\(([^\)]{1,20})\)"  # (제목)
    r"|\s+([가-힣a-zA-Z\s·,]{2,20}?)"  # 한글 제목 (짧은 것만)
    r")?"
)

def extract_title(first_line: str) -> str:
    tm = TITLE_RE.match(first_line)
    if not tm:
        return first_line[:30].strip()
    num  = tm.group(1)
    sub  = (tm.group(2) or tm.group(3) or tm.group(4) or "").strip()
    # 한글 제목인 경우 본문이 붙어있으면 제목 부분만
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


@st.cache_data(show_spinner=False)
def get_articles(doc_name: str, text: str, _v: int = 1) -> list[dict]:
    return parse_articles(doc_name, text)


# ─────────────────────────────────────────
# 6. 공통 UI — 조항 카드
# ─────────────────────────────────────────
DOC_COLORS = {
    "관리규약":          "#1a6ebd",
    "주차규약":          "#2e8b57",
    "커뮤니티센터 규약":  "#8b4513",
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
  <div style='font-size:0.88rem;color:#333;line-height:1.8;white-space:pre-wrap'>{content}</div>
</div>""")


# ─────────────────────────────────────────
# 7. 탭 구성
# ─────────────────────────────────────────
tab_keyword, tab_ai = st.tabs(["🔎 키워드 검색", "🤖 AI 질문 검색"])

# ══════════════════════════════════════════
# TAB A — 키워드 검색
# ══════════════════════════════════════════
with tab_keyword:
    col1, col2 = st.columns([4, 1])
    with col1:
        keyword = st.text_input(
            "검색어", placeholder="예: 층간소음, 주차 위반, 이용 시간",
            label_visibility="collapsed", key="keyword_input",
        )
    with col2:
        use_ai = st.toggle("🤖 AI 요약", value=False, disabled=not api_ready, key="ai_toggle")

    if keyword:
        kw = keyword.lower()
        matched: list[dict] = []
        for doc_name in selected:
            arts = get_articles(doc_name, pdf_texts[doc_name])
            title_hits = [a for a in arts if kw in a["title"].lower()]
            body_hits  = [a for a in arts if kw in a["content"].lower()
                          and kw not in a["title"].lower()]
            matched.extend(title_hits + body_hits)
        matched = matched[:10]

        if not matched:
            st.warning(f"**'{keyword}'** 에 해당하는 조항을 찾지 못했습니다.")
        else:
            st.success(f"총 **{len(matched)}개** 조항 발견")

            if use_ai and api_ready:
                cache_key = f"summary_{keyword}"
                if cache_key not in st.session_state:
                    docs = list({a["doc"] for a in matched})
                    ctx  = "\n\n".join(
                        f"=== [{n}] ===\n{pdf_texts[n]}" for n in docs if n in pdf_texts
                    )
                    ai_prompt = (
                        f"아파트 규약에서 '{keyword}' 관련 내용을 찾아 요약해줘.\n"
                        f"구체적인 기준(시간, 금액, 횟수 등)이 있으면 반드시 포함하고,\n"
                        f"관련 조항번호(규약명 + 조항번호)를 마지막에 명시해줘.\n"
                        f"서론 없이 바로 내용부터 시작해줘.\n\n[규약 전문]\n{ctx}"
                    )
                    with st.spinner("AI가 요약하는 중..."):
                        try:
                            st.session_state[cache_key] = ai_generate(ai_prompt)
                        except Exception as e:
                            st.warning(f"AI 요약 실패: {e}")
                            st.session_state[cache_key] = None

                if st.session_state.get(cache_key):
                    st.markdown("##### 🤖 AI 요약")
                    st.markdown(st.session_state[cache_key])

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

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 대화 초기화 버튼 (상단 고정)
    if st.session_state.get("messages"):
        if st.button("🗑️ 대화 초기화", key="clear_btn"):
            st.session_state.messages = []
            st.rerun()

    # 이전 대화 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("articles"):
                with st.expander("📋 관련 조항 원문 보기", expanded=False):
                    for art in msg["articles"]:
                        render_article_card(art)

    # 입력창 (Streamlit이 자동으로 하단 고정)
    if prompt := st.chat_input("질문을 입력하세요  (예: 방문차량 무료 주차는 몇 시간까지야?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI가 답변을 생성하는 중..."):
                try:
                    full_prompt = (
                        "너는 아파트 규약 전문 AI 비서야.\n"
                        "아래 규약 전문을 읽고 질문에 답변해줘.\n\n"
                        "규칙:\n"
                        "- 형식 레이블(\"핵심 답변:\", \"근거:\" 등) 없이 자연스럽게 답변해줘\n"
                        "- 답변 마지막에 근거 조항을 한 줄로 명시해줘 (예: 📌 관리규약 제16조)\n"
                        "- 질문과 직접 관련된 규약의 조항만 근거로 써줘\n"
                        "- 규약에 없는 내용은 \"해당 규약에서 찾을 수 없습니다\"라고만 답해줘\n\n"
                        f"[규약 전문]\n{combined_text}\n\n[질문]\n{prompt}"
                    )
                    response_text = ai_generate(full_prompt)
                    st.markdown(response_text)

                    # 근거 조항 원문 매칭
                    all_arts = []
                    for dn in selected:
                        all_arts += get_articles(dn, pdf_texts[dn])

                    ALIAS_MAP = {
                        "관리규약":         "관리규약",
                        "주차규약":         "주차규약",
                        "주차관리":         "주차규약",
                        "주차관리규정":     "주차규약",
                        "커뮤니티센터 규약": "커뮤니티센터 규약",
                        "커뮤니티규약":     "커뮤니티센터 규약",
                        "운영규정":         "커뮤니티센터 규약",
                    }

                    def extract_pairs(txt: str) -> list:
                        result  = []
                        clean   = re.sub(r"[^\w\s가-힣\(\)\.\,]", " ", txt)
                        doc_pat = re.compile(
                            r"(관리규약|주차규약|주차관리규정?|커뮤니티센터?\s*규약|운영규정)"
                        )
                        for dm in doc_pat.finditer(clean):
                            doc_name = ALIAS_MAP.get(dm.group(0).strip(), dm.group(0).strip())
                            after    = clean[dm.end():]
                            nxt      = doc_pat.search(after)
                            scope    = after[:nxt.start()] if nxt else after
                            for am in re.finditer(r"제\s*(\d+)\s*조", scope):
                                result.append((doc_name, am.group(1)))
                        return list(dict.fromkeys(result))

                    related   = []
                    seen_keys = set()
                    for doc_name, num in extract_pairs(response_text):
                        key = (doc_name, num)
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)
                        pat = re.compile(rf"제\s*{num}\s*조")
                        for art in all_arts:
                            if art["doc"] == doc_name and pat.search(art["title"]):
                                related.append(art)
                                break

                    if related:
                        with st.expander("📋 관련 조항 원문 보기", expanded=False):
                            for art in related:
                                render_article_card(art)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response_text,
                        "articles": related,
                    })

                except Exception as e:
                    st.error(f"❌ 오류 발생: {e}")
