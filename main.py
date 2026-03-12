import streamlit as st
import os
import sys

# 시작하자마자 어떤 라이브러리가 로드되는지 확인하기 위한 디버깅용
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores import Chroma
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain.chains.retrieval import create_retrieval_chain
    from langchain_core.prompts import ChatPromptTemplate
except ImportError as e:
    st.error(f"라이브러리 로딩 중 에러 발생: {e}")
    st.info("requirements.txt에 해당 모듈이 있는지 확인하고 Reboot 해주세요.")
    st.stop()

# API 키 설정
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🔑 Streamlit Secrets에 'GOOGLE_API_KEY'를 등록해주세요.")
    st.stop()

st.title("🏢 아파트 관리규약 AI 조서")

@st.cache_resource
def init_qa_chain(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    
    # 임베딩 및 벡터 저장
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = Chroma.from_documents(docs, embeddings)
    
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    
    prompt = ChatPromptTemplate.from_template("""
    아래 규약 내용을 바탕으로 질문에 답하세요. 
    내용이 없으면 관리사무소에 확인하라고 하세요.
    
    Context: {context}
    Question: {input}
    """)
    
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(vectorstore.as_retriever(), combine_docs_chain)

# 파일명 확인 (반드시 GitHub에 있는 파일명과 대소문자까지 일치해야 함)
PDF_FILE = "rules.pdf" 

qa_chain = init_qa_chain(PDF_FILE)

if qa_chain:
    if prompt := st.chat_input("궁금한 점을 물어보세요"):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            response = qa_chain.invoke({"input": prompt})
            st.markdown(response["answer"])
else:
    st.error(f"'{PDF_FILE}' 파일을 찾을 수 없습니다. GitHub 리포지토리에 파일을 업로드했는지 확인하세요.")

