import streamlit as st
import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains.retrieval import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate

# 1. API 키 설정 (Streamlit Secrets에서 가져오기)
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("⚠️ Streamlit Secrets에 'GOOGLE_API_KEY'가 설정되지 않았습니다.")
    st.stop()

st.set_page_config(page_title="아파트 관리규약 AI 조서", page_icon="🏢")
st.title("🏢 우리 아파트 관리규약 AI 조서")
st.info("관리규약 및 주차규약 PDF 내용을 바탕으로 AI가 답변합니다.")

# 2. RAG 엔진 초기화 (캐싱 처리하여 속도 최적화)
@st.cache_resource
def init_qa_chain(pdf_path):
    # PDF 로드 및 분할
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, 
        chunk_overlap=100,
        separators=["\n제", "\n\n", "\n", " "]
    )
    splits = text_splitter.split_documents(docs)
    
    # 임베딩 및 벡터 스토어 생성
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    
    # LLM 및 프롬프트 설정
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    
    system_prompt = (
        "당신은 아파트 관리규약 전문가입니다. "
        "제공된 규약 문맥(context)만을 사용하여 질문에 답하세요. "
        "답변 끝에는 반드시 '관련 규약 내용'을 참고하여 조항번호나 페이지를 언급하세요. "
        "만약 문맥에 내용이 없다면 '해당 내용은 규약에서 찾을 수 없습니다. 관리사무소에 문의해주세요.'라고 답하세요."
        "\n\n"
        "Context: {context}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{input}"),
        ]
    )
    
    # 체인 생성 (최신 LCEL 방식)
    combine_docs_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, combine_docs_chain)
    
    return retrieval_chain

# 3. PDF 파일 존재 확인 및 챗봇 실행
# GitHub 리포지토리에 업로드한 PDF 파일명을 여기에 적으세요. (예: rules.pdf)
pdf_file_path = "rules.pdf" 

if os.path.exists(pdf_file_path):
    qa_chain = init_qa_chain(pdf_file_path)
    
    # 채팅 히스토리 관리
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_input := st.chat_input("질문을 입력하세요 (예: 주차 위반 스티커 기준이 뭐야?)"):
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("규약에서 찾는 중..."):
                response = qa_chain.invoke({"input": user_input})
                answer = response["answer"]
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
else:
    st.error(f"❌ 파일을 찾을 수 없습니다: '{pdf_file_path}' 파일이 GitHub에 업로드되어 있는지 확인해주세요.")
