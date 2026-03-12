import streamlit as st
import google.generativeai as genai
import os

# 1. API 키 설정 및 디버깅
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("🔑 Secrets에 GOOGLE_API_KEY를 등록해주세요.")
    st.stop()

st.title("🏢 관리규약 AI (최종 에러 추적 모드)")

# 2. 규약 텍스트 (텍스트가 너무 길면 잘라서 테스트해보세요)
RULES_CONTEXT = """
(여기에 관리규약 내용을 붙여넣으세요. 
테스트를 위해 처음엔 한 페이지만 넣어보시는 것도 좋습니다.)
"""

# 사용 가능한 모델 리스트 출력용 (임시 추가)
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        st.write(f"사용 가능 모델: {m.name}")
        
# 3. 모델 설정 (에러 방지용 세이프가드)
# 안전 필터 때문에 응답이 거부되는 경우를 방지하기 위해 모든 필터를 끕니다.
safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
]

if user_input := st.chat_input("질문하세요"):
    with st.chat_message("user"): st.markdown(user_input)
    
    with st.chat_message("assistant"):
        try:
            # 모델 호출 시 안전 설정 적용
            model = genai.GenerativeModel('gemini-2.0-flash', safety_settings=safety_settings)
            
            # 프롬프트 생성
            prompt = f"다음 관리규약을 바탕으로 답변해줘:\n{RULES_CONTEXT}\n\n질문: {user_input}"
            
            response = model.generate_content(prompt)
            
            # 응답이 비어있거나 차단되었는지 확인
            if response.candidates:
                candidate = response.candidates[0]
                if candidate.finish_reason == 3: # SAFETY 에러
                    st.error("⚠️ AI가 안전 정책상 답변을 거부했습니다. (입력 내용 확인 필요)")
                elif candidate.content.parts:
                    answer = response.text
                    st.markdown(answer)
                else:
                    st.error(f"⚠️ 응답이 생성되었으나 내용이 없습니다. 사유: {candidate.finish_reason}")
            else:
                st.error("⚠️ AI 응답 후보(Candidate)가 생성되지 않았습니다.")
                
        except Exception as e:
            st.error(f"❌ 최종 에러 발생: {e}")
            if "quota" in str(e).lower():
                st.info("💡 API 사용량이 초과되었습니다. 잠시 후 시도하거나 새 키를 발급받으세요.")
            elif "400" in str(e):
                st.info("💡 요청 형식이 잘못되었습니다. (텍스트가 너무 길거나 API 설정 오류)")

