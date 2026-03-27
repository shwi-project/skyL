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

[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatInput"] textarea,
[data-testid="stTextInput"] input {
    font-family: 'Noto Sans KR', sans-serif !important;
}

[data-testid="stButton"] button p {
    font-size: 0.82rem !important;
}

[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    width: 24px !important;
    height: 24px !important;
    min-width: 24px !important;
}

[data-testid="stChatMessage"] {
    padding: 0.5rem !important;
    gap: 0.4rem !important;
}

[data-testid="stChatMessageAvatarAssistant"] {
    display: none !important;
}

[data-testid="stChatMessageAvatarUser"] {
    width: 24px !important;
    height: 24px !important;
    min-width: 24px !important;
}

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

[class*="profilePreview"] { display: none !important; }
[class*="_link_gzau3"] { display: none !important; }
[class*="viewerBadge"] { display: none !important; }

#MainMenu { display: none !important; }
[data-testid="stMainMenu"] { display: none !important; }
header [data-testid="stToolbar"] { display: none !important; }
header { display: none !important; }

.main .block-container { padding-top: 0 !important; }
[data-testid="stMainBlockContainer"] {
    padding-top: 1rem !important;
}
.st-emotion-cache-zy6yx3 {
    padding-top: 1rem !important;
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
    f"""<div style='display:flex;align-items:flex-start;margin-bottom:12px'>
    {logo_html}
    <div style='line-height:1.2'>
      <div style='font-size:1.1rem;font-weight:700'>롯데캐슬스카이엘 규약 통합 검색</div>
      <div style='font-size:0.78rem;color:#999;margin-top:2px'>우리아파트 규약을 키워드 및 AI로 검색합니다.</div>
    </div></div>""",
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────
# ⚙️ 컨텍스트 압축 설정
# ─────────────────────────────────────────
USE_CONTEXT_COMPRESSION = True
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

# ─────────────────────────────────────────
# 5. Gemini AI
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
# 10. 카드 렌더링
# ─────────────────────────────────────────
DOC_COLORS = {
    "관리규약":         "#1a6ebd",
    "주차규약":         "#2e8b57",
    "커뮤니티센터 규약": "#8b4513",
    "생활안내":         "#7b4f9e",
}

def render_article_card(art: dict, keyword: str = "", highlights: list[str] = None) -> None:
    content = art["content"]
    # 하이라이트 대상: 명시적 리스트 또는 단일 키워드
    terms = highlights if highlights else ([keyword] if keyword else [])
    for term in terms:
        if term:
            content = re.sub(
                f"(?i)({re.escape(term)})",
                r"<mark style='background:#fff3cd;padding:0 2px;border-radius:3px'>\1</mark>",
                content,
            )
    bc = DOC_COLORS.get(art["doc"], "#555")
    # 생활안내는 섹션 제목에서 > 이후만 표시
    display_title = art["title"].split(" > ")[-1] if " > " in art["title"] else art["title"]
    st.html(f"""
<div style='border:1px solid #e0e0e0;border-radius:10px;padding:16px 20px;
            margin-bottom:12px;background:#fafafa;box-shadow:0 1px 4px rgba(0,0,0,0.06)'>
  <div style='margin-bottom:8px'>
    <span style='background:{bc};color:white;padding:2px 8px;
                 border-radius:4px;font-size:0.75rem;font-weight:600'>{art["doc"]}</span>
    &nbsp;<span style='font-size:1rem;font-weight:700;color:#222'>{display_title}</span>
  </div>
  <div style='font-size:0.88rem;color:#333;line-height:1.8'>{content.replace(chr(10), '<br>')}</div>
</div>""")

# ─────────────────────────────────────────
# 11. 탭 구성
# ─────────────────────────────────────────
tab_keyword, tab_ai = st.tabs(["🔎 키워드 검색", "✦ AI 질문 검색"])

# ══════════════════════════════════════════
# TAB A — 키워드 검색 (규약 문서만)
# ══════════════════════════════════════════
with tab_keyword:
    if st.session_state.pop("_keyword_clear", False):
        st.session_state["keyword_input"] = ""
    keyword = st.text_input(
        "검색어", placeholder="예: 층간소음, 주차 위반, 이용 시간",
        label_visibility="collapsed", key="keyword_input",
    )

    # 키워드 검색은 규약 문서만 대상
    keyword_docs = [n for n in DOC_ORDER if n != "생활안내"]

    if keyword:
        # 동의어 확장: 입력 키워드 + 매핑된 규약 원문 용어
        search_terms = [keyword.lower()]
        for syn_key, syn_val in _SYNONYMS.items():
            if syn_key in keyword and syn_val.lower() not in search_terms:
                search_terms.append(syn_val.lower())

        matched: list[dict] = []
        for doc_name in keyword_docs:
            arts = get_articles(doc_name, pdf_texts[doc_name])
            doc_matched = []
            for a in arts:
                title_l = a["title"].lower()
                content_l = a["content"].lower()
                if any(t in title_l for t in search_terms):
                    doc_matched.append(a)
                elif any(t in content_l for t in search_terms):
                    doc_matched.append(a)
            matched.extend(doc_matched[:20])

        if not matched:
            st.warning(f"**'{keyword}'** 에 해당하는 조항을 찾지 못했습니다.")
        else:
            st.success(f"총 **{len(matched)}개** 조항 발견")
            st.divider()
            for art in matched:
                render_article_card(art, highlights=search_terms)

# ══════════════════════════════════════════
# TAB B — AI 질문 검색
# ══════════════════════════════════════════
with tab_ai:
    if not api_ready:
        st.error("API 키가 설정되지 않아 AI 검색을 사용할 수 없습니다.")
        st.stop()

    # 규약 선택 버튼
    ai_cols = st.columns(len(DOC_ORDER))
    for i, doc in enumerate(DOC_ORDER):
        with ai_cols[i]:
            is_active = st.session_state.selected_doc == doc
            if st.button(
                doc,
                key=f"doc_btn_{doc}",
                type="primary" if is_active else "secondary",
            ):
                st.session_state.selected_doc = doc
                st.rerun()

    selected = st.session_state.selected_doc

    for k in ("ai_question", "ai_response", "ai_articles"):
        if k not in st.session_state:
            st.session_state[k] = None if k != "ai_articles" else []

    # 문서별 시스템 프롬프트 분기
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
            return (
                f"[규약 전문]\n{context}\n\n"
                f"[질문]\n{question}\n\n"
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

    _PLACEHOLDERS = {
        "주차규약": "예: 방문차량 무료 주차는 몇 시간까지야?",
        "커뮤니티센터 규약": "예: 헬스장 이용시간이 어떻게 돼?",
        "관리규약": "예: 동대표 자격요건이 뭐야?",
        "생활안내": "예: 쓰레기 분리수거는 어떻게 해?",
    }
    if prompt := st.chat_input(_PLACEHOLDERS.get(selected, "질문을 입력하세요")):
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("AI가 답변을 생성하는 중..."):
                try:
                    all_arts = get_articles(selected, pdf_texts[selected])
                    context  = get_context_for_ai(selected, prompt, all_arts)
                    full_prompt = build_prompt(selected, context, prompt)

                    response_text = ai_generate(full_prompt)
                    response_text = re.sub(r"([^\n])\n*(📌)", r"\1\n\n\2", response_text)

                    st.markdown(response_text)

                    related = [] if selected == "생활안내" else find_related_articles(response_text, all_arts, selected)
                    if related:
                        with st.expander("📋 관련 내용 원문 보기", expanded=False):
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
                with st.expander("📋 관련 내용 원문 보기", expanded=False):
                    for art in st.session_state.ai_articles:
                        render_article_card(art)
