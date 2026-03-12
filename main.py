import streamlit as st
import os

# 1. 라이브러리 로드 (에러 추적 강화)
try:
    import langchain
    from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    from langchain.chains.combine_documents import create_stuff_documents_chain
    from langchain.chains.retrieval import create_retrieval_chain
    from langchain_core.prompts import ChatPromptTemplate
except ImportError as e:
    st.error(f"❌ 라이브러리 로드 실패: {e}")
    st.info("requirements.txt 파일을 다시 확인하고 App을 Reboot 해주세요.")
    st.stop()

# 2. API 키 설정
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🔑 Streamlit Secrets에 'GOOGLE_API_KEY'가 없습니다.")
    st.stop()

st.title("🏢 아파트 관리규약 AI 조서")

@st.cache_resource
def init_qa_chain(pdf_path):
    if not os.path.exists(pdf_path):
        return None
    
    try:
        loader = PyPDFLoader(pdf_path)
        pages = loader.load_and_split()
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = text_splitter.split_documents(pages)
        
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        # 가벼운 로컬 벡터 저장소 Chroma 사용
        vectorstore = Chroma.from_documents(documents=splits, embedding=embeddings)
        
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
        
        # 프롬프트 구성
        prompt = ChatPromptTemplate.from_template("""
        당신은 아파트 관리규약 전문가입니다. 아래 내용을 바탕으로 질문에 답하세요.
        내용이 없으면 관리사무소에 문의하라고 친절히 안내하세요.
        
        Context: {context}
        Question: {input}
        """)
        
        combine_docs_chain = create_stuff_documents_chain(llm, prompt)
        return create_retrieval_chain(vectorstore.as_retriever(), combine_docs_chain)
    except Exception as e:
        st.error(f"엔진 초기화 중 에러: {e}")
        return None

# 파일명 확인
PDF_FILE = "rules.pdf" 

if os.path.exists(PDF_FILE):
    qa_chain = init_qa_chain(PDF_FILE)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if user_input := st.chat_input("질문하세요"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            response = qa_chain.invoke({"input": user_input})
            st.markdown(response["answer"])
            st.session_state.messages.append({"role": "assistant", "content": response["answer"]})
else:
    st.warning(f"⚠️ '{PDF_FILE}' 파일이 없습니다. GitHub 상위 폴더에 업로드해주세요.")
