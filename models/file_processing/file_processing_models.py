from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import time


class VectorStoreResponse(BaseModel):
    message: str = Field(..., description="Message indicating the success or failure of the operation")
    num_documents: int = Field(..., description="Number of documents in the vector store")
    collection_name: Optional[str] = Field(..., description="Name of the collection")
    createdAt: int = Field(
        default_factory=lambda: int(time.time()),
        description="Epoch timestamp when the vector store was created"
    )
    updatedAt: int = Field(
        default_factory=lambda: int(time.time()),
        description="Epoch timestamp when the vector store was last updated"
    )


class FileConversionResponse(BaseModel):
    message: str = Field(..., description="Message indicating the success or failure of the operation")
    original_filename: str = Field(..., description="Original filename of the uploaded file")
    gcp_urls: Optional[List[str]] = Field(None, description="List of GCP urls to upload the file")
    createdAt: int = Field(
        default_factory=lambda: int(time.time()),
        description="Epoch timestamp when the vector store was created"
    )
    updatedAt: int = Field(
        default_factory=lambda: int(time.time()),
        description="Epoch timestamp when the vector store was last updated"
    )

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None