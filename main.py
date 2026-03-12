import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA

# 1. API 키 설정 (Streamlit Secrets 활용)
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("🔑 Secrets에 GOOGLE_API_KEY를 등록해주세요.")
    st.stop()

st.set_page_config(page_title="아파트 규약 AI", page_icon="🏢")
st.title("🏢 원당역 롯데캐슬스카이엘 규약 봇")

# 2. PDF 파싱 및 FAISS 벡터 DB 구축 (캐싱하여 매번 새로 읽지 않도록 방지)
@st.cache_resource
def load_and_build_vector_db():
    pdf_path = "rules.pdf"
    if not os.path.exists(pdf_path):
        return None
    
    # PDF 읽기 및 텍스트 분할 (조항 단위로 잘릴 수 있도록 청크 설정)
    loader = PyPDFLoader(pdf_path)
    docs = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    splits = text_splitter.split_documents(docs)
    
    # 임베딩 및 FAISS 인덱스 생성 (임베딩도 무료 티어 사용)
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = FAISS.from_documents(documents=splits, embedding=embeddings)
    
    # 검색 엔진(Retriever) 설정: 가장 유사한 3개의 조항만 가져옴
    return vectorstore.as_retriever(search_kwargs={"k": 3})

retriever = load_and_build_vector_db()

if retriever is None:
    st.warning("⚠️ 'rules.pdf' 파일이 없습니다. GitHub에 PDF 파일을 업로드해주세요.")
    st.stop()

# 3. LLM 설정 (토큰 소모가 적고 빠른 Flash 모델 사용)
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True # 출처 확인용
)

# 4. 채팅 UI 구성
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("예: 층간소음 관리위원회 개최 기준이 어떻게 돼?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("규약을 검색 중입니다..."):
            try:
                # FAISS에서 검색 후 답변 생성
                response = qa_chain.invoke({"query": prompt})
                answer = response["result"]
                
                # 참고한 페이지(출처) 추출
                sources = set([doc.metadata.get('page', 0) + 1 for doc in response["source_documents"]])
                source_text = f"\n\n*(참고 페이지: {', '.join(map(str, sources))}p)*"
                
                final_answer = answer + source_text
                st.markdown(final_answer)
                st.session_state.messages.append({"role": "assistant", "content": final_answer})
                
            except Exception as e:
                st.error(f"❌ 에러가 발생했습니다: {e}")




