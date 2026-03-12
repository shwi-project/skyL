import streamlit as st
import os

# [강력 조치] 라이브러리 로드 순서 및 에러 핸들링
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores import Chroma
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain.chains import create_retrieval_chain
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain_core.prompts import ChatPromptTemplate
except Exception as e:
    st.error(f"⚠️ 라이브러리 구성 에러: {e}")
    st.info("requirements.txt의 라이브러리들이 서버에 설치되는 중일 수 있습니다. 1~2분 후 Reboot 해주세요.")
    st.stop()

# API 키 설정
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🔑 Streamlit Secrets에 'GOOGLE_API_KEY'를 등록해주세요.")
    st.stop()

st.title("🏢 우리 아파트 관리규약 AI")

@st.cache_resource
def init_bot(pdf_path):
    if not os.path.exists(pdf_path): return None
    
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    splits = text_splitter.split_documents(docs)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    # FAISS 대신 설치가 훨씬 쉬운 Chroma 사용
    vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
    
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    
    prompt = ChatPromptTemplate.from_template("""
    당신은 아파트 관리규약 전문가입니다. 아래 내용을 바탕으로 답변하세요.
    Context: {context}
    Question: {input}
    """)
    
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    return create_retrieval_chain(vectorstore.as_retriever(), combine_docs_chain)

# PDF 파일명 (GitHub에 올린 파일명과 일치해야 함)
PDF_FILE = "rules.pdf" 

if os.path.exists(PDF_FILE):
    qa_chain = init_bot(PDF_FILE)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if user_input := st.chat_input("질문을 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"): st.markdown(user_input)

        with st.chat_message("assistant"):
            res = qa_chain.invoke({"input": user_input})
            st.markdown(res["answer"])
            st.session_state.messages.append({"role": "assistant", "content": res["answer"]})
else:
    st.warning(f"'{PDF_FILE}' 파일을 찾을 수 없습니다. GitHub에 업로드해주세요.")
