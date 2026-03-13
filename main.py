import streamlit as st
import google.generativeai as genai
import os
import re
from pypdf import PdfReader

# ─────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────
st.set_page_config(page_title="아파트 규약 검색", page_icon="🏢", layout="wide")

st.title("🏢 아파트 규약 통합 검색")
st.caption("관리규약 · 주차규약 · 커뮤니티센터 규약을 키워드 및 AI로 검색합니다.")

# ─────────────────────────────────────────
# 1. API 키 설정
# ─────────────────────────────────────────
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
    api_ready = True
except Exception:
    st.warning("⚠️ Streamlit Cloud의 Settings > Secrets에 GOOGLE_API_KEY를 등록해주세요.")
    api_ready = False

# ─────────────────────────────────────────
# 2. PDF 텍스트 추출
# ─────────────────────────────────────────
PDF_FILES = {
    "관리규약":         "rules_management.pdf",
    "주차규약":         "rules_parking.pdf",
    "커뮤니티센터 규약": "rules_community.pdf",
}

@st.cache_data
def load_pdf_text(pdf_path: str) -> str:
    if not os.path.exists(pdf_path):
        return ""
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    except Exception as e:
        st.error(f"PDF 읽기 오류 ({pdf_path}): {e}")
    return text

pdf_texts: dict[str, str] = {}
for name, path in PDF_FILES.items():
    t = load_pdf_text(path)
    if t:
        pdf_texts[name] = t

if not pdf_texts:
    st.error(
        "📂 GitHub 저장소 최상위 경로에 다음 PDF 파일을 업로드해주세요:\n\n"
        "- `rules_management.pdf` (관리규약)\n"
        "- `rules_parking.pdf` (주차규약)\n"
        "- `rules_community.pdf` (커뮤니티센터 규약)"
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

combined_text = ""
for name in selected:
    combined_text += f"\n\n=== [{name}] ===\n{pdf_texts[name]}"

# ─────────────────────────────────────────
# 4. 모델 초기화
# ─────────────────────────────────────────
@st.cache_resource
def get_model():
    """사용 가능한 Gemini 모델을 우선순위대로 반환."""
    try:
        available = {m.name for m in genai.list_models()
                     if "generateContent" in m.supported_generation_methods}
    except Exception:
        available = set()

    candidates = [
        "models/gemini-2.0-flash-lite",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-flash-8b",
    ]
    for name in candidates:
        if not available or name in available:
            return genai.GenerativeModel(name.replace("models/", ""))
    return genai.GenerativeModel("gemini-1.5-flash")

# ─────────────────────────────────────────
# 5. 조/항 단위 파싱 (목차 제외)
# ─────────────────────────────────────────
ARTICLE_PATTERN = re.compile(
    r"(제\s*\d+\s*조(?:의\s*\d+)?[\s\S]*?)(?=제\s*\d+\s*조(?:의\s*\d+)?|\Z)"
)

def is_toc_block(block: str) -> bool:
    """목차성 블록인지 판단 — 내용이 거의 없고 짧으면 목차로 간주."""
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if len(lines) <= 2:
        return True
    # 실제 본문이 없고 조항 제목만 나열된 경우 (한 줄당 20자 미만이 대부분)
    content_lines = lines[1:]  # 첫 줄(제목) 제외
    if content_lines and all(len(l) < 25 for l in content_lines):
        return True
    return False

def parse_articles(text: str) -> list[dict]:
    articles = []
    for m in ARTICLE_PATTERN.finditer(text):
        block = m.group(0).strip()
        if not block:
            continue
        if is_toc_block(block):
            continue  # 목차 블록 제외
        first_line = block.splitlines()[0].strip()
        articles.append({"title": first_line, "content": block})
    return articles

@st.cache_data
def get_all_articles(doc_name: str, text: str) -> list[dict]:
    arts = parse_articles(text)
    for a in arts:
        a["doc"] = doc_name
    return arts

# ─────────────────────────────────────────
# 6. 탭 구성
# ─────────────────────────────────────────
tab_keyword, tab_ai = st.tabs(["🔎 키워드 검색", "🤖 AI 질문 검색"])

# ══════════════════════════════════════════
# TAB A — 키워드 검색 (조/항 단위 + AI 요약)
# ══════════════════════════════════════════
with tab_keyword:
    st.subheader("키워드 검색")

    col1, col2 = st.columns([4, 1])
    with col1:
        keyword = st.text_input(
            "검색어", placeholder="예: 층간소음, 주차 위반, 이용 시간",
            label_visibility="collapsed",
        )
    with col2:
        use_ai_summary = st.toggle("🤖 AI 요약", value=True, disabled=not api_ready)

    if keyword:
        keyword_lower = keyword.lower()
        matched_articles: list[dict] = []

        for doc_name in selected:
            articles = get_all_articles(doc_name, pdf_texts[doc_name])

            # 조항 파싱이 안 된 PDF는 라인 기반 fallback
            if not articles:
                lines = pdf_texts[doc_name].splitlines()
                for i, line in enumerate(lines):
                    if keyword_lower in line.lower():
                        start = max(0, i - 2)
                        end   = min(len(lines), i + 4)
                        block = "\n".join(lines[start:end])
                        matched_articles.append({
                            "doc": doc_name,
                            "title": f"{i+1}번째 줄",
                            "content": block,
                        })
            else:
                for art in articles:
                    if keyword_lower in art["content"].lower():
                        matched_articles.append(art)

        if not matched_articles:
            st.warning(f"'{keyword}'에 해당하는 조항을 찾지 못했습니다.")
        else:
            st.success(f"총 **{len(matched_articles)}개** 조항 발견")

            # ── AI 요약 ──────────────────────────
            if use_ai_summary and api_ready:
                summary_context = "\n\n".join(
                    f"[{a['doc']}] {a['content']}" for a in matched_articles
                )
                summary_prompt = f"""
아래는 아파트 규약에서 '{keyword}' 키워드로 검색된 조항들이야.
핵심 내용을 3~5줄로 간결하게 요약해줘. 규약 이름과 조항 번호를 반드시 포함해줘.

{summary_context}
"""
                with st.spinner("AI가 검색 결과를 요약하는 중..."):
                    try:
                        resp = get_model().generate_content(summary_prompt)
                        if resp.text:
                            with st.container(border=True):
                                st.markdown("#### 🤖 AI 요약")
                                st.markdown(resp.text)
                    except Exception as e:
                        st.warning(f"AI 요약 실패: {e}")

            st.divider()

            # ── 조항별 expander ──────────────────
            for art in matched_articles:
                highlighted = re.sub(
                    f"(?i)({re.escape(keyword)})",
                    r"**:orange[\1]**",
                    art["content"],
                )
                with st.expander(f"📄 [{art['doc']}]  {art['title']}", expanded=False):
                    st.markdown(highlighted)

# ══════════════════════════════════════════
# TAB B — AI 질문 검색 (관련 조항 원문 포함)
# ══════════════════════════════════════════
with tab_ai:
    st.subheader("AI 질문 검색")

    if not api_ready:
        st.error("API 키가 설정되지 않아 AI 검색을 사용할 수 없습니다.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 대화 기록 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("articles"):
                with st.expander("📋 관련 조항 원문 보기"):
                    for art in msg["articles"]:
                        st.markdown(f"**[{art['doc']}] {art['title']}**")
                        st.caption(art["content"])
                        st.divider()

    if prompt := st.chat_input("질문을 입력하세요  (예: 관리위원회 구성 요건이 뭐야?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("규약 전문을 검토 중입니다..."):
                try:
                    full_prompt = f"""
너는 아파트 규약 전문 AI 비서야.
아래 [규약 전문]을 꼼꼼히 읽고 [질문]에 대해 규약에 근거하여 정확하고 친절하게 답변해줘.

답변 형식을 반드시 지켜줘:
1. 핵심 답변을 먼저 간결하게 (3줄 이내)
2. 근거 조항: 규약명과 조항 번호 명시 (예: 관리규약 제15조 제2항)
3. 규약에 없는 내용은 "해당 규약에서 찾을 수 없습니다"라고 답해줘

[규약 전문]
{combined_text}

[질문]
{prompt}
"""
                    response = get_model().generate_content(full_prompt)

                    if response.text:
                        st.markdown(response.text)

                        # AI 답변에서 언급된 조항 원문 자동 첨부
                        all_articles = []
                        for doc_name in selected:
                            all_articles += get_all_articles(doc_name, pdf_texts[doc_name])

                        mentioned_nums = set(re.findall(r"제\s*(\d+)\s*조", response.text))
                        related_arts = []
                        for num in mentioned_nums:
                            pat = re.compile(rf"제\s*{num}\s*조")
                            for art in all_articles:
                                if pat.search(art["title"]) and art not in related_arts:
                                    related_arts.append(art)

                        if related_arts:
                            with st.expander("📋 관련 조항 원문 보기"):
                                for art in related_arts:
                                    st.markdown(f"**[{art['doc']}] {art['title']}**")
                                    st.caption(art["content"])
                                    st.divider()

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response.text,
                            "articles": related_arts,
                        })
                    else:
                        st.error("답변을 생성하지 못했습니다.")

                except Exception as e:
                    st.error(f"❌ 오류 발생: {e}")

    if st.session_state.messages:
        if st.button("🗑️ 대화 초기화"):
            st.session_state.messages = []
            st.rerun()
