import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os

# 1. API 키 설정 및 디버깅
if "GOOGLE_API_KEY" in st.secrets:
    api_key = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=api_key)
else:
    st.error("🔑 Secrets에 GOOGLE_API_KEY가 없습니다!")
    st.stop()

st.title("🏢 관리규약 AI (최종 디버깅)")

# 2. PDF 텍스트 추출
@st.cache_resource
def get_pdf_content(pdf_path):
    if not os.path.exists(pdf_path): return None
    reader = PdfReader(pdf_path)
    return "".join([page.extract_text() for page in reader.pages])

PDF_FILE = "rules.pdf"
rules_context = get_pdf_content(PDF_FILE)

# 3. 모델 가용성 체크 (404 방지 핵심)
try:
    # 현재 키로 사용 가능한 모델들을 리스트업합니다.
    available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    
    # 만약 리스트에 gemini-1.5-flash가 없으면 첫 번째 모델을 강제로 선택합니다.
    target_model = 'models/gemini-1.5-flash'
    if target_model not in available_models:
        target_model = available_models[0] if available_models else None
        
    if not target_model:
        st.error("사용 가능한 Gemini 모델이 없습니다. API 키를 확인해주세요.")
        st.stop()
except Exception as e:
    st.error(f"모델 목록 확인 중 에러: {e}")
    st.stop()

# 4. 채팅 로직
if user_input := st.chat_input("질문하세요"):
    with st.chat_message("user"): st.markdown(user_input)
    
    with st.chat_message("assistant"):
        try:
            model = genai.GenerativeModel(target_model)
            prompt = f"다음 규약을 참고해 답해줘: {rules_context[:10000]}\n\n질문: {user_input}" # 컨텍스트 제한(안전빵)
            
            response = model.generate_content(prompt)
            st.markdown(response.text)
        except Exception as e:
            st.error(f"응답 생성 에러: {e}")
            st.info(f"시도한 모델명: {target_model}")
