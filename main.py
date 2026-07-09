import os
import fitz 
import streamlit as st
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex,SimpleField,SearchableField
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

load_dotenv()

search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
search_key = os.getenv("AZURE_SEARCH_KEY")
index_name = os.getenv("AZURE_SEARCH_INDEX")

print(search_endpoint)
print(search_key)
print(index_name)

openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_KEY"), # change name to api_key(s) if required
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION") 
)

def create_index():
    index_client = SearchIndexClient(
        endpoint = search_endpoint,
        credential = AzureKeyCredential(search_key)
    )
    fields = [
        SimpleField(name = "id" , type = "Edm.string" ,key=True ),
        SearchableField(name = "content" , type = "Edm.string"),

    ]
    index = SearchIndex(name=index_name,fields=fields)
    index_client.create_or_update_index(index)

if "index_created" not in st.session_state:
    try:
        create_index()
        st.session_state.index_created = True
    except:
        st.session_state.index_created = True

st.title("📄 SMART-RAG")
st.caption("Upload two PDFs , Ask anything from them")

st.subheader("Step1 - Upload a PDF ")
uploaded_file1 = st.file_uploader("Choose a PDF file ", type = "pdf ")

st.subheader("Step 2 - Upload another PDF")
uploaded_file2 = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file1 and uploaded_file2:
    # Extract text from PDF
    doc1 = fitz.open(stream=uploaded_file1.read(), filetype="pdf")
    text = ""
    for page in doc1:
        text += page.get_text()
    doc1.close()

    doc2 = fitz.open(stream=uploaded_file2.read(), filetype="pdf")
    for page in doc2:
        text += page.get_text()
    doc2.close()

    # Split into chunks
    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]

    # Index into Azure AI Search
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=AzureKeyCredential(search_key)
    )
    documents = [{"id": str(i), "content": chunk} for i, chunk in enumerate(chunks)]
    search_client.upload_documents(documents)

    st.success(f"✅ Uploaded {len(chunks)} chunks from {uploaded_file1.name} and {uploaded_file2.name} combined")



    # Step 2 - Ask a question
    st.subheader("Step 3 — Ask a question")
    question = st.text_input("Type your question here...")

    if st.button("Ask"):
        # Search Azure AI Search
        results = search_client.search(question, top=3)
        context = " ".join([r["content"] for r in results])

        # Ask Azure OpenAI
        response = openai_client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            messages=[
                {"role": "system", "content": f"Answer only from this document: {context}"},
                {"role": "user", "content": question}
            ],
            max_tokens=300
        )

        st.write("**Answer:**")
        st.write(response.choices[0].message.content)