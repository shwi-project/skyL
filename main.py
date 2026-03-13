import streamlit as st
import requests
import os
import re
from pypdf import PdfReader

# ─────────────────────────────────────────
# 페이지 설정
# ─────────────────────────────────────────
st.set_page_config(page_title="롯데캐슬스카이엘 규약 검색", page_icon="🦅", layout="wide")
st.title("🦅🏰 롯데캐슬스카이엘 규약 통합 검색")
st.caption("관리규약 · 주차규약 · 커뮤니티센터 규약을 키워드 및 AI로 검색합니다.")

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
# 2. PDF별 텍스트 정제 함수
# ─────────────────────────────────────────

def is_toc_page(text: str) -> bool:
    """목차 페이지 여부 판단 — · 문자가 많거나 줄점(……) 패턴이 많으면 목차."""
    dot_count = text.count('·') + text.count('…') + text.count('‥')
    return dot_count > 8

def clean_management(text: str) -> str:
    """관리규약 PDF 전용 정제: 분리된 글자 복원, 목차 제거."""
    if is_toc_page(text):
        return ""
    # 페이지 번호 제거 '- N -'
    text = re.sub(r'-\s*\d+\s*-\n?', '', text)
    # '제 조N 【제목】' → '제N조 (제목)'  (조 뒤에 숫자)
    text = re.sub(r'제\s*조\s*(\d+)\s*【\s*([^】]*?)\s*】', r'제\1조 (\2)', text)
    # '제N조 【제목】' 또는 '제 N 조 【제목】' → '제N조 (제목)'
    text = re.sub(
        r'제\s*(\d+)\s*조(?:의\s*\d+)?\s*【\s*([^】]*?)\s*】',
        lambda m: f'제{m.group(1)}조 ({m.group(2).strip()})',
        text
    )
    # 남은 【 】 괄호 정리
    text = re.sub(r'【\s*([^】]*?)\s*】', r'(\1)', text)
    # 제N조 앞에 줄바꿈 삽입 (붙어있는 경우)
    text = re.sub(r'(?<!\n)(제\s*\d+\s*조)', r'\n\n\1', text)
    # 장(章) 앞에도 줄바꿈
    text = re.sub(r'(?<!\n)(제\s*\d+\s*장)', r'\n\n\1', text)
    # ①②③ 등 항번호 앞에 줄바꿈
    text = re.sub(r'(?<!\n)([①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])', r'\n\1', text)
    # 과도한 공백 정리
    text = re.sub(r'[ \t]{3,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def clean_parking(text: str) -> str:
    """주차규약 PDF 전용 정제: 붙어있는 조항 분리."""
    if is_toc_page(text):
        return ""
    # '제N조 (제목)' 앞에 줄바꿈 삽입
    text = re.sub(r'(?<!\n)(제\d+조)', r'\n\n\1', text)
    # 장(章) 앞에도 줄바꿈
    text = re.sub(r'(?<!\n)(제\d+장)', r'\n\n\1', text)
    # ①②③ 등 항번호 앞에 줄바꿈
    text = re.sub(r'(?<!\n)([①②③④⑤⑥⑦⑧⑨⑩])', r'\n\1', text)
    # 숫자 목록 '1. ' '2. ' 앞에 줄바꿈
    text = re.sub(r'(?<!\n)(\d+\. )', r'\n\1', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def clean_community(text: str) -> str:
    """커뮤니티센터 규약 PDF 전용 정제."""
    if is_toc_page(text):
        return ""
    text = re.sub(r'-\s*\d+\s*-\n?', '', text)
    # 제N조 앞에 줄바꿈
    text = re.sub(r'(?<!\n)(제\d+조)', r'\n\n\1', text)
    text = re.sub(r'(?<!\n)(제\d+장)', r'\n\n\1', text)
    text = re.sub(r'(?<!\n)([⓵⓶⓷⓸⓹⓺⓻⓼⓽⓾①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮])', r'\n\1', text)
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# ─────────────────────────────────────────
# 3. PDF 로드
# ─────────────────────────────────────────
PDF_FILES = {
    "관리규약":         ("rules_management.pdf",  clean_management),
    "주차규약":         ("rules_parking.pdf",      clean_parking),
    "커뮤니티센터 규약": ("rules_community.pdf",    clean_community),
}

@st.cache_data
def load_pdf_text(pdf_path: str, cleaner_name: str) -> str:
    """PDF에서 텍스트 추출 후 정제. cleaner_name은 캐시 키 구분용."""
    cleaner_map = {
        "management": clean_management,
        "parking":    clean_parking,
        "community":  clean_community,
    }
    cleaner = cleaner_map[cleaner_name]

    if not os.path.exists(pdf_path):
        return ""
    pages = []
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            raw = page.extract_text() or ""
            cleaned = cleaner(raw)
            if cleaned:
                pages.append(cleaned)
    except Exception as e:
        st.error(f"PDF 읽기 오류 ({pdf_path}): {e}")
    return "\n\n".join(pages)

CLEANER_KEYS = {
    "관리규약":         "management",
    "주차규약":         "parking",
    "커뮤니티센터 규약": "community",
}

pdf_texts: dict[str, str] = {}
for name, (path, _) in PDF_FILES.items():
    t = load_pdf_text(path, CLEANER_KEYS[name])
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
# 4. 검색 대상 선택
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
# 5. AI 모델 초기화
# ─────────────────────────────────────────
def ai_generate(prompt: str) -> str:
    """Gemini REST API 직접 호출 — 429 시 최대 3회 재시도."""
    import time
    api_key = st.session_state.get("GOOGLE_API_KEY", "")
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512},
    }
    for attempt in range(3):
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 429:
            wait = (attempt + 1) * 10
            time.sleep(wait)
            continue
        if not resp.ok:
            raise RuntimeError(f"API 오류 {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    raise RuntimeError(f"429 한도 초과 — 마지막 응답: {resp.text[:500]}")

# ─────────────────────────────────────────
# 6. 조/항 단위 파싱
# ─────────────────────────────────────────
ARTICLE_PATTERN = re.compile(
    r"(제\s*\d+\s*조(?:의\s*\d+)?[^\n]*\n[\s\S]*?)(?=\n제\s*\d+\s*조(?:의\s*\d+)?|\Z)"
)

def parse_articles(doc_name: str, text: str) -> list[dict]:
    """조(條) 단위로 텍스트를 파싱. 목차성 블록은 제외."""
    articles = []
    for m in ARTICLE_PATTERN.finditer(text):
        block = m.group(0).strip()
        if not block:
            continue
        lines = [l for l in block.splitlines() if l.strip()]
        # 목차 필터: 줄 수가 2줄 이하 OR 실제 내용이 없는 블록
        if len(lines) <= 2:
            continue
        # 목차 필터: 내용 줄이 모두 매우 짧고 점선 패턴
        body_lines = lines[1:]
        if body_lines and sum(1 for l in body_lines if len(l.strip()) < 20) / len(body_lines) > 0.7:
            continue
        title = lines[0].strip()
        articles.append({"doc": doc_name, "title": title, "content": block})
    return articles

@st.cache_data
def get_all_articles(doc_name: str, text: str) -> list[dict]:
    return parse_articles(doc_name, text)

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
            label_visibility="collapsed",
        )
    with col2:
        use_ai_summary = st.toggle("🤖 AI 요약", value=False, disabled=not api_ready)

    if keyword:
        keyword_lower = keyword.lower()
        matched: list[dict] = []

        for doc_name in selected:
            articles = get_all_articles(doc_name, pdf_texts[doc_name])
            if articles:
                # 제목에 키워드 있는 것 우선, 본문만 있는 것 후순위
                title_match = [a for a in articles if keyword_lower in a["title"].lower()]
                body_match  = [a for a in articles if keyword_lower in a["content"].lower()
                               and keyword_lower not in a["title"].lower()]
                matched.extend(title_match + body_match)

        # 최대 10개로 제한
        matched = matched[:10]

        if not matched:
            st.warning(f"**'{keyword}'** 에 해당하는 조항을 찾지 못했습니다.")
        else:
            st.success(f"총 **{len(matched)}개** 조항 발견")

            # AI 요약
            if use_ai_summary and api_ready:
                # 요약용: 조항당 200자로 제한해 토큰 절약
                ctx_items = [f"[{a['doc']}] {a['title']}\n{a['content'][:200]}" for a in matched[:8]]
                ctx = "\n\n".join(ctx_items)
                prompt = (
                    f"아파트 규약에서 '{keyword}' 키워드로 검색된 조항들이야.\n"
                    f"핵심 내용을 3~5줄로 간결하게 요약해줘. 규약 이름과 조항 번호를 반드시 포함해줘.\n\n"
                    f"{ctx}"
                )
                with st.spinner("AI가 검색 결과를 요약하는 중..."):
                    try:
                        result = ai_generate(prompt)
                        if result:
                            st.html(f"""
<div style='background:linear-gradient(135deg,#f0f7ff,#e8f4fd);
            border-left:4px solid #1a6ebd;border-radius:0 10px 10px 0;
            padding:16px 20px;margin-bottom:8px'>
  <div style='font-weight:700;color:#1a6ebd;font-size:1rem;margin-bottom:8px'>
    🤖 AI 요약
  </div>
  <div style='font-size:0.9rem;color:#333;line-height:1.8;white-space:pre-wrap'>{result}</div>
</div>""")
                    except Exception as e:
                        st.warning(f"AI 요약 실패: {e}")

            st.divider()

            # 조항별 카드 표시
            DOC_COLORS = {
                "관리규약":         "#1a6ebd",
                "주차규약":         "#2e8b57",
                "커뮤니티센터 규약": "#8b4513",
            }
            for art in matched:
                highlighted = re.sub(
                    f"(?i)({re.escape(keyword)})",
                    r"<mark style='background:#fff3cd;padding:0 2px;border-radius:3px'>\1</mark>",
                    art["content"],
                )
                badge_color = DOC_COLORS.get(art["doc"], "#555")
                badge = (
                    f"<span style='background:{badge_color};color:white;"
                    f"padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600'>"
                    f"{art['doc']}</span>"
                )
                title_html = (
                    f"<span style='font-size:1rem;font-weight:700;color:#222'>"
                    f"{art['title']}</span>"
                )
                body_html = (
                    "<div style='font-size:0.88rem;color:#333;line-height:1.7;"
                    "white-space:pre-wrap;margin-top:8px'>"
                    + highlighted + "</div>"
                )
                card_html = f"""
<div style='border:1px solid #e0e0e0;border-radius:10px;padding:16px 20px;
            margin-bottom:12px;background:#fafafa;
            box-shadow:0 1px 4px rgba(0,0,0,0.06)'>
  <div style='margin-bottom:6px'>{badge}&nbsp;&nbsp;{title_html}</div>
  {body_html}
</div>"""
                st.html(card_html)

# ══════════════════════════════════════════
# TAB B — AI 질문 검색
# ══════════════════════════════════════════
with tab_ai:
    if not api_ready:
        st.error("API 키가 설정되지 않아 AI 검색을 사용할 수 없습니다.")
        st.stop()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("articles"):
                with st.expander("📋 관련 조항 원문 보기", expanded=False):
                    DOC_COLORS3 = {
                        "관리규약": "#1a6ebd",
                        "주차규약": "#2e8b57",
                        "커뮤니티센터 규약": "#8b4513",
                    }
                    for art in msg["articles"]:
                        bc = DOC_COLORS3.get(art["doc"], "#555")
                        st.html(f"""
<div style='border:1px solid #e0e0e0;border-radius:10px;padding:14px 18px;
            margin-bottom:10px;background:#fafafa'>
  <div style='margin-bottom:6px'>
    <span style='background:{bc};color:white;padding:2px 8px;
                 border-radius:4px;font-size:0.75rem;font-weight:600'>{art["doc"]}</span>
    &nbsp;<span style='font-weight:700;font-size:0.95rem'>{art["title"]}</span>
  </div>
  <div style='font-size:0.85rem;color:#444;line-height:1.7;white-space:pre-wrap'>{art["content"]}</div>
</div>""")

    if prompt := st.chat_input("질문을 입력하세요  (예: 방문차량 무료 주차는 몇 시간까지야?)"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("관련 조항을 검색 중입니다..."):
                try:
                    # ── 질문에서 키워드 추출 후 관련 조항만 필터링 ──
                    # 조사/어미 제거 후 2글자 이상 단어만 추출
                    q_words = [w for w in re.split(r"[\s,?!.]+", prompt) if len(w) >= 2]

                    all_arts = []
                    for dn in selected:
                        all_arts += get_all_articles(dn, pdf_texts[dn])

                    # 각 키워드가 하나라도 포함된 조항 수집 (최대 15개)
                    relevant = []
                    seen = set()
                    for art in all_arts:
                        text_lower = art["content"].lower()
                        if any(w.lower() in text_lower for w in q_words):
                            key = (art["doc"], art["title"])
                            if key not in seen:
                                seen.add(key)
                                relevant.append(art)
                        if len(relevant) >= 15:
                            break

                    # 관련 조항이 없으면 전체에서 앞 5개만 사용
                    if not relevant:
                        relevant = all_arts[:5]

                    # 최대 8개, 조항당 300자로 잘라서 토큰 절약
                    relevant = relevant[:8]
                    ctx_parts = []
                    for a in relevant:
                        body = a["content"][:300].strip()
                        ctx_parts.append(f"[{a['doc']}] {a['title']}\n{body}")
                    ctx = "\n\n".join(ctx_parts)

                    full_prompt = f"""너는 아파트 규약 전문 AI 비서야.
아래 [관련 조항]을 바탕으로 [질문]에 간결하고 정확하게 답변해줘.

답변 형식:
1. 핵심 답변 (3줄 이내)
2. 근거: 규약명 + 조항번호 (예: 주차규약 제20조)
3. 규약에 없으면 "해당 내용을 찾을 수 없습니다"라고 답해줘

[관련 조항]
{ctx}

[질문]
{prompt}"""

                    response_text = ai_generate(full_prompt)

                    if response_text:
                        st.markdown(response_text)

                        # 답변에서 언급된 조항 번호 추출 → 원문 첨부
                        all_arts = []
                        for doc_name in selected:
                            all_arts += get_all_articles(doc_name, pdf_texts[doc_name])

                        mentioned = set(re.findall(r"제\s*(\d+)\s*조", response_text))
                        related = []
                        for num in mentioned:
                            pat = re.compile(rf"제\s*{num}\s*조")
                            for art in all_arts:
                                if pat.search(art["title"]) and art not in related:
                                    related.append(art)

                        if related:
                            with st.expander("📋 관련 조항 원문 보기", expanded=False):
                                DOC_COLORS2 = {
                                    "관리규약": "#1a6ebd",
                                    "주차규약": "#2e8b57",
                                    "커뮤니티센터 규약": "#8b4513",
                                }
                                for art in related:
                                    bc = DOC_COLORS2.get(art["doc"], "#555")
                                    st.html(f"""
<div style='border:1px solid #e0e0e0;border-radius:10px;padding:14px 18px;
            margin-bottom:10px;background:#fafafa'>
  <div style='margin-bottom:6px'>
    <span style='background:{bc};color:white;padding:2px 8px;
                 border-radius:4px;font-size:0.75rem;font-weight:600'>{art["doc"]}</span>
    &nbsp;<span style='font-weight:700;font-size:0.95rem'>{art["title"]}</span>
  </div>
  <div style='font-size:0.85rem;color:#444;line-height:1.7;white-space:pre-wrap'>{art["content"]}</div>
</div>""")

                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": response_text,
                            "articles": related,
                        })
                    else:
                        st.error("답변을 생성하지 못했습니다.")

                except Exception as e:
                    st.error(f"❌ 오류 발생: {e}")

    if st.session_state.messages:
        if st.button("🗑️ 대화 초기화"):
            st.session_state.messages = []
            st.rerun()
