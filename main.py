import streamlit as st
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

# 페이지 설정
st.set_page_config(page_title="아파트 관리규약 AI", page_icon="🏢")
st.title("🏢 아파트 관리규약 AI 비서")
st.info("관리규약이나 주차규약에 대해 궁금한 점을 물어보세요.")

# API 키 설정 (Streamlit Secrets에서 불러옴)
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("API 키가 설정되지 않았습니다. Streamlit 설정에서 추가해주세요.")
    st.stop()

@st.cache_resource
def load_and_index_pdf():
    # PDF 파일은 깃허브 레파지토리에 함께 업로드해두세요.
    pdf_path = "apt_rules.pdf" 
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
    return vectorstore

# 엔진 준비
try:
    vectorstore = load_and_index_pdf()
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    qa_chain = RetrievalQA.from_chain_type(
        llm=llm, chain_type="stuff", 
        retriever=vectorstore.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True
    )
except Exception as e:
    st.error(f"PDF 로드 중 오류 발생: {e}")
    st.stop()

# 채팅 인터페이스
query = st.text_input("질문을 입력하세요:", placeholder="예: 주차 위반 시 과태료는 얼마인가요?")

if query:
    with st.spinner("규약에서 찾는 중..."):
        result = qa_chain.invoke({"query": query})
        st.markdown("### 🤖 답변")
        st.write(result["result"])
        
        with st.expander("📌 근거 조항 확인"):
            for doc in result["source_documents"]:
                st.write(f"- {doc.page_content[:200]}...")