import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Milvus
from langchain_community.embeddings import HuggingFaceEmbeddings
from config.settings import settings

class FileProcessingRepo:
    def __init__(self):
        self.pdf_loader = PyPDFLoader
        self.CHUNK_SIZE = 1200
        self.CHUNK_OVERLAP = 150
        self.embeddings_model = "sentence-transformers/all-mpnet-base-v2"

    def load_and_chunk_pdfs(self, pdf_folder_path, gcp_urls_map=None):
        documents = []
        gcp_urls_map = gcp_urls_map or {}

        for file in os.listdir(pdf_folder_path):
            if file.endswith('.pdf'):
                pdf_path = os.path.join(pdf_folder_path, file)
                loader = PyPDFLoader(pdf_path)
                docs = loader.load()

                gcp_url = gcp_urls_map.get(file)
                for doc in docs:
                    if gcp_url:
                        doc.metadata['gcp_url'] = gcp_url

                documents.extend(docs)

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=self.CHUNK_SIZE, chunk_overlap=self.CHUNK_OVERLAP)
        chunked_docs = text_splitter.split_documents(documents)
        return chunked_docs

    def create_milvus_vectorstore(self, documents, collection_name):
        """
        Create a Milvus vector store with the given documents
        
        Args:
            documents: List of documents to vectorize
            collection_name: Collection name for Milvus
            
        Returns:
            Milvus vector store instance
        """
        embeddings = HuggingFaceEmbeddings(model_name=self.embeddings_model)
        cleaned_docs = [self.clean_metadata(doc) for doc in documents]

        # Add project_id to metadata
        for doc in cleaned_docs:
            doc.metadata['collection_name'] = collection_name

        vector_store = Milvus.from_documents(
            documents=cleaned_docs,
            embedding=embeddings,
            collection_name=collection_name,
            connection_args={"uri": settings.MILVUS_URI, "token": settings.MILVUS_TOKEN},
            drop_old=False
        )
        print(f"Vector store created with collection name: {collection_name}")
        return vector_store

    from langchain_core.documents import Document

    def clean_metadata(self, doc: Document) -> Document:
        if not doc.metadata:
            return doc

        safe_fields = {'source', 'page', 'filename', 'project_id', 'gcp_url'}
        cleaned_metadata = {
            k: v for k, v in doc.metadata.items()
            if k in safe_fields
        }
        doc.metadata = cleaned_metadata
        return doc


file_processing_repo = FileProcessingRepo()