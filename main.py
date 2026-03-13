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
# 1. API 키 설정 (Streamlit secrets 사용)
# ─────────────────────────────────────────
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
    api_ready = True
except Exception:
    st.warning("⚠️ Streamlit Cloud의 Settings > Secrets에 GOOGLE_API_KEY를 등록해주세요.")
    api_ready = False

# ─────────────────────────────────────────
# 2. PDF 텍스트 추출 (파일별 캐싱)
# ─────────────────────────────────────────
PDF_FILES = {
    #"관리규약":        "rules_management.pdf",
    "관리규약":        "rules_parking.pdf",
    "주차규약":        "rules_parking.pdf",
    "커뮤니티센터 규약": "rules_parking.pdf",
    #"커뮤니티센터 규약": "rules_community.pdf",
}

@st.cache_data
def load_pdf_text(pdf_path: str) -> str:
    """PDF 파일에서 텍스트를 추출합니다."""
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

# 모든 PDF 로드
pdf_texts: dict[str, str] = {}
for name, path in PDF_FILES.items():
    text = load_pdf_text(path)
    if text:
        pdf_texts[name] = text

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

# 선택된 규약 텍스트 합치기
combined_text = ""
for name in selected:
    combined_text += f"\n\n=== [{name}] ===\n{pdf_texts[name]}"

# ─────────────────────────────────────────
# 4. 검색 모드 탭
# ─────────────────────────────────────────
tab_keyword, tab_ai = st.tabs(["🔎 키워드 검색", "🤖 AI 질문 검색"])

# ── 4-A. 키워드 검색 ─────────────────────
with tab_keyword:
    st.subheader("키워드 검색")
    keyword = st.text_input("검색어를 입력하세요", placeholder="예: 층간소음, 주차 위반, 이용 시간")

    if keyword:
        keyword_lower = keyword.lower()
        results = []

        for doc_name in selected:
            doc_text = pdf_texts[doc_name]
            lines = doc_text.splitlines()
            for i, line in enumerate(lines):
                if keyword_lower in line.lower():
                    # 앞뒤 2줄 컨텍스트 포함
                    start = max(0, i - 2)
                    end   = min(len(lines), i + 3)
                    context = "\n".join(lines[start:end])
                    # 키워드 하이라이트
                    highlighted = re.sub(
                        f"(?i)({re.escape(keyword)})",
                        r"**:orange[\1]**",
                        context
                    )
                    results.append((doc_name, i + 1, highlighted))

        if results:
            st.success(f"총 **{len(results)}**건 발견")
            for doc_name, line_no, ctx in results:
                with st.expander(f"📄 {doc_name} — {line_no}번째 줄"):
                    st.markdown(ctx)
        else:
            st.warning(f"'{keyword}'에 해당하는 내용을 찾지 못했습니다.")

# ── 4-B. AI 질문 검색 ────────────────────
with tab_ai:
    st.subheader("AI 질문 검색")

    if not api_ready:
        st.error("API 키가 설정되지 않아 AI 검색을 사용할 수 없습니다.")
        st.stop()

    # 모델 초기화 (캐싱)
    @st.cache_resource
    def get_model():
        available = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        name = (
            "models/gemini-2.0-flash" if "models/gemini-2.0-flash" in available
            else "models/gemini-1.5-flash"
        )
        return genai.GenerativeModel(name)

    model = get_model()

    # 대화 기록 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 대화 기록 표시
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 입력
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
답변 시 반드시 어떤 규약의 몇 조(항)에 해당하는지 출처를 명시해줘.
규약에 없는 내용은 "해당 규약에서 찾을 수 없습니다"라고 솔직하게 답해줘.

[규약 전문]
{combined_text}

[질문]
{prompt}
                    """
                    response = model.generate_content(full_prompt)

                    if response.text:
                        st.markdown(response.text)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": response.text}
                        )
                    else:
                        st.error("답변을 생성하지 못했습니다.")

                except Exception as e:
                    st.error(f"❌ 오류 발생: {e}")

    # 대화 초기화 버튼
    if st.session_state.messages:
        if st.button("🗑️ 대화 초기화"):
            st.session_state.messages = []
            st.rerun()

