import time
from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentReference(BaseModel):
    source: str = Field(..., description="Original filename or source identifier")
    page: int = Field(..., description="1-indexed page number in source document")
    content: str = Field(..., description="First 100 characters of relevant content")
    doc_id: str = Field(..., description="Unique document identifier in storage system")
    score: Optional[float] = Field(None, description="Retrieval relevance score (0-1)")
    gcp_url: Optional[str] = Field(None, description="GCP signed URL for the source document")

class ChatMessage(BaseModel):
    role: str = Field(..., description="Either 'user' or 'assistant'")
    content: str = Field(..., description="The message text content")
    sources: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of source references in format {'type': 'DocID|Source', 'reference': 'id123'}"
    )

class ChatRequest(BaseModel):
    question: Optional[str] = Field(..., description="The new user question to answer")
    is_audio: bool = Field(default=False, description="Whether the input is an audio URL")
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio data if is_audio is True")
    audio_url: Optional[str] = Field(None, description="URL to the audio file if is_audio is True")
    collection_name: str = Field(..., description="Milvus collection to query")
    session_id: Optional[str] = Field(None, description="Unique session identifier for chat history")
    chat_history: List[ChatMessage] = Field(
        default_factory=list,
        description="Previous messages in chronological order"
    )
    chat_language: str = Field(None, description="Language in which the chat is generated")
    llm: str = Field(
        model="gpt-4o",
        description="Which LLM to use for generation"
    )

class ChatResponse(BaseModel):
    role: str = Field("assistant", description="Always 'assistant' for responses")
    content: str = Field(..., description="Generated answer with inline citations")
    sources: List[Dict[str, str]] = Field(
        ...,
        description="Formatted source references [{'type': 'DocID', 'reference': 'id123'}]"
    )
    collection: str = Field(..., description="Name of collection that was queried")
    timestamp: int = Field(
        default_factory=lambda: int(time.time()),
        description="Unix epoch response time"
    )

class CollectionSummaryRequest(BaseModel):
    collection_name: str = Field(..., description="Milvus collection to summarize")
    summary_length: str = Field(
        default="short",
        description="Length of summary: 'short', 'medium', or 'detailed'",
    )
    llm: str = Field(default="gpt-4", description="Which LLM to use for summarization")
    max_docs: int = Field(
        default=100,
        description="Maximum documents to process",
        ge=1,
        le=500
    )

class CollectionSummaryResponse(BaseModel):
    collection: str = Field(..., description="Name of summarized collection")
    summary: str = Field(..., description="Generated summary of documents")
    document_count: int = Field(..., description="Number of documents processed")
    timestamp: int = Field(
        default_factory=lambda: int(time.time()),
        description="When summary was generated"
    )

class DeleteCollectionRequest(BaseModel):
    collection_name: str = Field(..., description="Name of the collection to delete")
    confirm: bool = Field(default=False, description="Must be True to actually delete")

class DeleteCollectionResponse(BaseModel):
    success: bool = Field(..., description="Whether deletion was successful")
    collection_name: str = Field(..., description="Name of deleted collection")
    message: str = Field(..., description="Status message")
    timestamp: int = Field(
        default_factory=lambda: int(time.time()),
        description="When deletion was attempted"
    )