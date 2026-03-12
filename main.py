import streamlit as st
import os

# 1. 라이브러리 임포트 체크
try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain.chains.retrieval import create_retrieval_chain
    from langchain_core.prompts import ChatPromptTemplate
except ImportError as e:
    st.error(f"❌ 라이브러리 로드 실패: {e}")
    st.info("requirements.txt 수정 후 앱을 Reboot 해주세요.")
    st.stop()

# 2. API 키 및 설정
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🔑 Streamlit Secrets에 'GOOGLE_API_KEY'를 등록해주세요.")
    st.stop()

st.set_page_config(page_title="아파트 관리규약 AI", page_icon="🏢")
st.title("🏢 아파트 관리규약 AI 조서")

# 3. RAG 엔진 초기화
@st.cache_resource
def init_qa_chain(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    
    try:
        loader = PyPDFLoader(pdf_path)
        docs = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        splits = text_splitter.split_documents(docs)
        
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        # FAISS 대신 Chroma 사용 (설치가 훨씬 안정적입니다)
        vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
        
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
        
        system_prompt = (
            "당신은 아파트 관리규약 전문가입니다. "
            "Context: {context}"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
        ])
        
        combine_docs_chain = create_stuff_documents_chain(llm, prompt)
        return create_retrieval_chain(vectorstore.as_retriever(), combine_docs_chain)
    except Exception as e:
        st.error(f"엔진 초기화 중 오류: {e}")
        return None

# 파일명 (GitHub에 올린 파일명과 일치해야 함)
PDF_FILE = "rules.pdf" 

if os.path.exists(PDF_FILE):
    qa_chain = init_qa_chain(PDF_FILE)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("질문하세요"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            response = qa_chain.invoke({"input": user_input})
            answer = response["answer"]
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
else:
    st.warning(f"⚠️ {PDF_FILE} 파일을 찾을 수 없습니다. GitHub에 업로드해주세요.")
