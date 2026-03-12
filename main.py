import streamlit as st
import google.generativeai as genai
import os
from pypdf import PdfReader

# 1. API 키 설정
API_KEY = st.secrets.get("GOOGLE_API_KEY", "AIzaSyBA-tHdAaJE4RsVuOtGohrhR5KOZKf926Q")
genai.configure(api_key=API_KEY)

st.set_page_config(page_title="아파트 규약 AI", page_icon="🏢")
st.title("🏢 관리규약 AI 조서")

# 2. PDF에서 텍스트 직접 추출 (캐싱하여 속도 최적화)
@st.cache_data
def load_pdf_text():
    pdf_path = "rules.pdf"
    if not os.path.exists(pdf_path):
        return None
    
    text = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text
    except Exception as e:
        st.error(f"PDF 읽기 오류: {e}")
        return None

rules_text = load_pdf_text()

if not rules_text:
    st.warning("⚠️ 깃허브 최상위 경로에 'rules.pdf' 파일을 업로드해주세요.")
    st.stop()

# 3. 모델 설정 (긴 문맥 처리에 강한 최신 Flash 모델)
# 사용 가능한 모델을 자동으로 찾습니다.
available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
model_name = 'models/gemini-2.0-flash' if 'models/gemini-2.0-flash' in available_models else 'models/gemini-1.5-flash'
model = genai.GenerativeModel(model_name)

# 4. 채팅 UI
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("질문을 입력하세요 (예: 층간소음 관리위원회 구성 요건이 뭐야?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("규약 전문을 검토 중입니다..."):
            try:
                # PDF 전체 내용과 질문을 한 번에 전달
                full_prompt = f"""
                너는 아파트 동대표를 돕는 AI 비서야. 
                아래 [관리규약 전문]을 꼼꼼히 읽고, [질문]에 대해 규약에 근거하여 정확하고 친절하게 답변해줘.
                
                [관리규약 전문]
                {rules_text}
                
                [질문]
                {prompt}
                """
                response = model.generate_content(full_prompt)
                
                if response.text:
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                else:
                    st.error("답변을 생성하지 못했습니다.")
            except Exception as e:
                st.error(f"❌ 에러 발생: {e}")
