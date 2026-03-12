import streamlit as st
import google.generativeai as genai
import os

# 1. API 키 설정
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("🔑 Secrets에 API 키를 등록해주세요.")
    st.stop()

st.title("🏢 우리 아파트 관리규약 AI")

# 2. 관리규약 텍스트 직접 입력 (여기에 PDF 내용을 복사해서 붙여넣으세요)
# 내용이 너무 길면 별도의 .txt 파일로 만들어서 읽어도 되지만, 
# 에러를 피하기 위해 일단 여기에 직접 붙여넣는 걸 추천합니다.
RULES_CONTEXT = """
여기에 관리규약 전체 내용을 복사해서 붙여넣으세요.
제1조(목적) ...
제2조(용어의 정의) ...
(중략)
주차규약 제n조...
"""

# 3. 채팅 UI
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if user_input := st.chat_input("규약에 대해 물어보세요"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)

    with st.chat_message("assistant"):
        try:
            # 모델 호출
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = f"""
            당신은 아파트 관리규약 전문가입니다. 아래 제공된 [규약내용]을 바탕으로 답변하세요.
            내용이 없으면 관리사무소에 문의하라고 안내하고, 답변 끝에는 관련 조항을 언급하세요.

            [규약내용]
            {RULES_CONTEXT}

            질문: {user_input}
            """
            
            response = model.generate_content(prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            st.error(f"응답 생성 에러: {e}")
