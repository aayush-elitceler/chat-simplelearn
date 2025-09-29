from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class UploadStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ProjectBase(BaseModel):
    name: str
    userId: str
    collectionName: str
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    uploadStatus: Optional[UploadStatus] = None
    blobKeys: Optional[List[str]] = None

class Project(ProjectBase):
    id: str
    projectId: Optional[str] = None  # Made optional, will be set from collectionName
    uploadStatus: UploadStatus = UploadStatus.PENDING
    blobKeys: List[str] = Field(default_factory=list)
    createdAt: datetime
    updatedAt: datetime

    class Config:
        from_attributes = True
    
    @field_validator('createdAt', 'updatedAt', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except ValueError:
                try:
                    return datetime.fromisoformat(v)
                except ValueError:
                    return datetime.now()
        return v
    
    def __init__(self, **data):
        super().__init__(**data)
        # Set projectId from collectionName if not provided
        if not self.projectId and hasattr(self, 'collectionName'):
            self.projectId = self.collectionName

class ProjectResponse(BaseModel):
    message: str
    project: Project 