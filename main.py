import os
import sys
import subprocess

# 1. 🛡️ 무적의 자가 복구 방어막 (절대 지우지 마세요!)
# Streamlit이 requirements.txt를 무시하더라도 강제로 환경을 세팅합니다.
def ensure_environment():
    try:
        import langchain.chains
        import faiss
        import pypdf
    except ImportError:
        import streamlit as st
        with st.spinner("초기 서버 환경을 구성 중입니다. 잠시만 기다려주세요..."):
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "-q",
                "langchain", "langchain-community", "langchain-google-genai", 
                "langchain-text-splitters", "pypdf", "faiss-cpu", "google-generativeai"
            ])
            
ensure_environment()

# 2. 🚀 본 코드 시작
import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

# API 키 설정 (Secrets 우선, 없으면 하드코딩된 값 사용)
API_KEY = st.secrets.get("GOOGLE_API_KEY", "AIzaSyBA-tHdAaJE4RsVuOtGohrhR5KOZKf926Q")
os.environ["GOOGLE_API_KEY"] = API_KEY

st.set_page_config(page_title="아파트 규약 AI", page_icon="🏢")
st.title("🏢 관리규약 AI 조서")

# 3. PDF 읽기 및 FAISS 벡터 DB 구축
@st.cache_resource
def get_retriever():
    pdf_path = "rules.pdf"
    if not os.path.exists(pdf_path):
        return None
    
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
    return vectorstore.as_retriever(search_kwargs={"k": 3})

retriever = get_retriever()

if retriever is None:
    st.warning("⚠️ 깃허브 최상위 경로에 'rules.pdf' 파일을 업로드해주세요.")
    st.stop()

# 4. LLM 설정
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True
)

# 5. 채팅 UI
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("질문을 입력하세요 (예: 층간소음 규정이 어떻게 돼?)"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("규약을 확인하고 있습니다..."):
            try:
                response = qa_chain.invoke({"query": prompt})
                answer = response["result"]
                
                # 출처 페이지 번호 추출
                sources = set([doc.metadata.get('page', 0) + 1 for doc in response["source_documents"]])
                source_text = f"\n\n*(참고: 관리규약 {', '.join(map(str, sources))}페이지)*"
                
                final_answer = answer + source_text
                st.markdown(final_answer)
                st.session_state.messages.append({"role": "assistant", "content": final_answer})
            except Exception as e:
                st.error(f"❌ 에러 발생: {e}")
