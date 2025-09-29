from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
import time

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"

class VectorStoreTaskResponse(BaseModel):
    task_id: str = Field(..., description="Unique task identifier")
    status: ProcessingStatus = Field(..., description="Current processing status")
    gcp_urls: Optional[list[str]] = Field(
        None, description="List of GCP URLs for uploaded files"
    )
    progress: float = Field(0.0, description="Completion percentage 0-100")
    collection_name: Optional[str] = Field(None)
    num_documents: Optional[int] = Field(None)
    message: Optional[str] = Field(None)
    timestamp: int = Field(default_factory=lambda: int(time.time()))