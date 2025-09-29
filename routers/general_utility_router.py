from fastapi import APIRouter, Depends

from models.user import UserData
from repository.general_utilities.general_utility_repo import general_utility_repo
from utility.auth_middleware import auth_middleware

router = APIRouter(
    prefix="/api/v1/generalUtility",
    tags=["File Processing Router"]
)


@router.get("/{collection_name}/createNewSession")
async def create_session(
    collection_name: str,
    current_user: UserData = Depends(auth_middleware)
):
    try:
        session, chat, created_new_session = await general_utility_repo.create_session_and_chat(collection_name, current_user)

        return {
            "message": "Session and chat creation endpoint",
            "session": session,
            "chat": chat,
            "createdNewSession": created_new_session
        }
    except Exception as e:
        return {
            "error": str(e)
        }

@router.get("/{collection_name}/createSessionName/{session_id}")
async def create_session_name(
    collection_name: str,
    session_id: str,
    current_user: UserData = Depends(auth_middleware)
):
    try:
        session_name = await general_utility_repo.gen_chat_name(session_id, collection_name, current_user)

        return {
            "message": "Session name generation endpoint",
            "sessionName": session_name
        }
    except Exception as e:
        return {
            "error": str(e)
        }