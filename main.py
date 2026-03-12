import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os

# 1. API 키 설정 (Streamlit Secrets에서 가져오기)
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("🔑 Streamlit Secrets에 'GOOGLE_API_KEY'를 등록해주세요.")
    st.stop()

st.set_page_config(page_title="아파트 관리규약 AI", page_icon="🏢")
st.title("🏢 우리 아파트 관리규약 AI 조서")

# 2. PDF에서 텍스트 추출 (복잡한 라이브러리 배제)
@st.cache_resource
def get_pdf_content(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        return full_text
    except Exception as e:
        st.error(f"PDF 읽기 에러: {e}")
        return None

# GitHub에 올린 PDF 파일명 확인
PDF_FILE = "rules.pdf" 
rules_context = get_pdf_content(PDF_FILE)

if rules_context:
    # 3. 채팅 UI 구성
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("규약에 대해 궁금한 점을 물어보세요"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            try:
                # 4. Gemini 모델 호출 (Context를 직접 주입하는 방식)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                prompt = f"""
                당신은 아파트 관리규약 전문가입니다. 
                아래 제공된 [관리규약] 내용을 바탕으로 질문에 친절하게 답변하세요.
                내용이 규약에 없다면 관리사무소에 문의하라고 안내하세요.
                답변 끝에는 반드시 관련 조항번호를 언급하세요.

                [관리규약]
                {rules_context}

                질문: {user_input}
                """
                
                response = model.generate_content(prompt)
                answer = response.text
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
            except Exception as e:
                st.error(f"AI 응답 생성 중 에러가 발생했습니다: {e}")
else:
    st.error(f"❌ '{PDF_FILE}' 파일을 찾을 수 없습니다. GitHub 리포지토리에 파일을 올려주세요.")
