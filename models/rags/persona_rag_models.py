from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from models.rags import ChatRequest


class PersonaChatRequest(ChatRequest):
    persona: str = Field("default", description="Professional persona: ux, sales, technical, management, default")

class PersonaChatResponse(BaseModel):
    response: str
    sources: List[Dict]
    session_id: str
    chat_id: str
    persona: str
    is_new_session: bool
    transcribed_text: Optional[str] = None