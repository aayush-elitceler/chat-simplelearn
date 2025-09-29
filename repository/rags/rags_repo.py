import asyncio
import os
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_community.vectorstores import Milvus
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.prompts import MessagesPlaceholder, ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnableParallel, RunnableLambda
from operator import itemgetter
from pymilvus import connections, Collection
from langchain.storage import LocalFileStore
from langchain.embeddings import CacheBackedEmbeddings
import threading

import prompts
from config.settings import settings
from prompts import get_rag_sys_prompt


class RagRepo:
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo-16k",
            temperature=0.8,
            api_key=settings.OPENAI_API_KEY
        )
        underlying_embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        fs = LocalFileStore("./embedding_cache")
        self.embeddings = CacheBackedEmbeddings.from_bytes_store(
            underlying_embeddings,
            fs,
            namespace=underlying_embeddings.model_name
        )

        self._preloaded_collections = set()
        self._preload_lock = threading.Lock()

    def _ensure_collection_loaded(self, collection_name: str):
        with self._preload_lock:
            if collection_name not in self._preloaded_collections:
                connections.connect(
                    alias="default",
                    uri=settings.MILVUS_URI,
                    token=settings.MILVUS_TOKEN
                )
                try:
                    Collection(collection_name).load()
                    self._preloaded_collections.add(collection_name)
                finally:
                    connections.disconnect("default")

    def _get_retriever(self, collection_name: str):
        self._ensure_collection_loaded(collection_name)
        return Milvus(
            embedding_function=self.embeddings,
            collection_name=collection_name,
            connection_args={
                "uri": settings.MILVUS_URI,
                "token": settings.MILVUS_TOKEN
            },
            search_params={
                "metric_type": "L2",
                "params": {"nprobe": 10}
            },
            consistency_level="Eventually"
        ).as_retriever(search_kwargs={"k": 10})

    async def _aget_retriever(self, collection_name: str):
        self._ensure_collection_loaded(collection_name)
        return Milvus(
            embedding_function=self.embeddings,
            collection_name=collection_name,
            connection_args={
                "uri": settings.MILVUS_URI,
                "token": settings.MILVUS_TOKEN
            },
            search_params={
                "metric_type": "L2",
                "params": {"nprobe": 10}
            },
            consistency_level="Eventually"
        ).as_retriever(search_kwargs={"k": 5})

    def _format_docs(self, docs: List[Document]) -> str:
        formatted = []
        for i, doc in enumerate(docs):
            formatted.append(
                f"Document excerpt {i + 1}:\n"
                f"Content: {doc.page_content}\n"
                f"---"
            )
        return "\n".join(formatted)

    def get_chat_chain(self, collection_name: str):
        retriever = self._get_retriever(collection_name)

        def debug_retrieval(inputs):
            print(f"\n🔍 Retrieving docs for: '{inputs['question']}'")
            docs = retriever.get_relevant_documents(inputs["question"])
            print(f"📄 Found {len(docs)} documents")
            return {
                "context": self._format_docs(docs),
                "question": inputs["question"],
                "chat_history": inputs["chat_history"]
            }

        prompt = ChatPromptTemplate.from_messages([
            ("system", prompts.rag_prompt.RAG_SYS_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])

        return (
                RunnableParallel({
                    "question": itemgetter("question"),
                    "chat_history": itemgetter("chat_history")
                })
                | RunnableLambda(debug_retrieval)
                | prompt
                | self.llm
        )

    async def aget_chat_chain(self, collection_name: str, chat_language: str = "en"):
        retriever = await self._aget_retriever(collection_name)

        async def async_retrieval(inputs):
            print(f"\n🔍 Retrieving docs for: '{inputs['question']}'")
            docs = await retriever.aget_relevant_documents(inputs["question"])
            print(f"📄 Found {len(docs)} documents")
            return {
                "context": self._format_docs(docs),
                "question": inputs["question"],
                "chat_history": inputs["chat_history"]
            }

        rag_prompt = get_rag_sys_prompt(chat_language)

        prompt = ChatPromptTemplate.from_messages([
            ("system", rag_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ])

        return (
                RunnableParallel({
                    "question": itemgetter("question"),
                    "chat_history": itemgetter("chat_history")
                })
                | RunnableLambda(async_retrieval)
                | prompt
                | self.llm
        )


    def get_collection_documents(self, collection_name: str, max_docs: int = 100) -> List[Document]:
        connections.connect(
            alias="default",
            uri=settings.MILVUS_URI,
            token=settings.MILVUS_TOKEN
        )

        try:
            collection = Collection(collection_name)
            collection.load()
            doc_count = collection.num_entities
            all_docs = []
            BATCH_SIZE = min(50, max_docs)

            for i in range(0, min(doc_count, max_docs), BATCH_SIZE):
                res = collection.query(
                    expr="",
                    offset=i,
                    limit=BATCH_SIZE,
                    output_fields=["*"]
                )
                all_docs.extend(res)

            return [Document(
                page_content=d.get("text", ""),
                metadata={k: v for k, v in d.items() if k != "text"}
            ) for d in all_docs]

        finally:
            connections.disconnect("default")

    def _get_vector_store(self, collection_name: str):
        return Milvus(
            embedding_function=self.embeddings,
            collection_name=collection_name,
            connection_args={
                "uri": settings.MILVUS_URI,
                "token": settings.MILVUS_TOKEN
            }
        )

    def _extract_sources_from_docs(self, docs):
        sources = []
        for doc in docs:
            source_info = {
                "source": doc.metadata.get('source', 'Unknown'),
                "page": doc.metadata.get('page', 1),
                "gcp_url": doc.metadata.get('gcp_url'),  # Extract GCP URL
                "content": doc.page_content[:100] + "..." if len(doc.page_content) > 100 else doc.page_content
            }
            sources.append(source_info)
        return sources

    async def _aget_additional_insights(self, collection_name: str, question: str, context_docs: List[Document]) -> \
    Dict[str, Any]:
        try:
            all_docs = self.get_collection_documents(collection_name, max_docs=50)
            formatted_all_docs = self._format_docs(all_docs)
            formatted_context_docs = self._format_docs(context_docs)

            summary_prompt = PromptTemplate.from_template("""
            Based on the following documents from the collection, provide a concise 3-line summary:

            {documents}

            Summary:
            """)

            stats_prompt = PromptTemplate.from_template("""
            Analyze the following documents and extract the most important statistics, numbers, 
            or quantitative data. Focus on key metrics, figures, and measurable information:

            {documents}

            Important Statistics:
            """)

            missing_prompt = PromptTemplate.from_template("""
            Given the user's question: "{question}"
            And the context documents retrieved: {context_docs}
            And the broader collection content: {all_docs}

            What information seems to be missing from our collection that would help answer 
            this question more completely? Consider gaps in data, time periods, or topics.

            Missing Information:
            """)

            tasks = [
                self.llm.ainvoke(summary_prompt.format(documents=formatted_all_docs)),
                self.llm.ainvoke(stats_prompt.format(documents=formatted_all_docs)),
                self.llm.ainvoke(missing_prompt.format(
                    question=question,
                    context_docs=formatted_context_docs,
                    all_docs=formatted_all_docs
                ))
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            return {
                "summary": str(results[0].content) if not isinstance(results[0],
                                                                     Exception) else "Error generating summary",
                "important_stats": str(results[1].content) if not isinstance(results[1],
                                                                             Exception) else "Error extracting statistics",
                "missing_info": str(results[2].content) if not isinstance(results[2],
                                                                          Exception) else "Error identifying missing information"
            }

        except Exception as e:
            return {
                "summary": f"Error: {str(e)}",
                "important_stats": f"Error: {str(e)}",
                "missing_info": f"Error: {str(e)}"
            }


rags_repo = RagRepo()