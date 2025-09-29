import cuid
from fastapi import HTTPException

from repository.ai_utilities import ai_utility_repo
from services.supabase_client import supabase_client



class GeneralUtilityRepo:
    def __init__(self):
        pass

    async def create_session_and_chat(self, collection_name: str, current_user):
        project = supabase_client.get_project_by_collection_name(collection_name)

        session_id = cuid.cuid()
        session_name = "New Chat"
        session_data = {
            "id": session_id,
            "name": session_name,
            "projectId": project["id"],
            "userId": current_user.id,
            "createdAt": "NOW()",
            "updatedAt": "NOW()",
        }
        session = supabase_client.create_session(session_data)
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        chat = supabase_client.create_or_get_chat_for_session(session_id, project["id"], current_user.id)
        if not chat:
            raise HTTPException(status_code=500, detail="Failed to create or get chat")

        print(f"Created new session: {session_id} with name '{session_name}' and chat: {chat['id']}")
        created_new_session = True
        return session, chat, created_new_session

    async def gen_chat_name(self, session_id: str, collection_name: str, current_user) -> str:
        project = supabase_client.get_project_by_collection_name(collection_name)
        chat = supabase_client.create_or_get_chat_for_session(session_id, project["id"], current_user.id)

        session_name = await ai_utility_repo.generate_session_name(
            question=chat,
            project_name=project.get("name")
        )
        return session_name

general_utility_repo = GeneralUtilityRepo()