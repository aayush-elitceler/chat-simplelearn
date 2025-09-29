import json
from supabase import create_client
from config.settings import settings
from typing import Optional, Dict, Any
import cuid


class SupabaseClient:
    def __init__(self):
        """Initialize Supabase client with credentials"""
        try:
            if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
                raise ValueError("Supabase credentials not properly configured")

            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            print("Successfully initialized Supabase client")

        except Exception as e:
            print(f"Failed to initialize Supabase client: {str(e)}")
            self.client = None

    # ---------------------- Users ----------------------
    def ensure_user_exists(self, user_id: str, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Ensure a user exists in the User table; create if missing.
        Returns the user record (at least with id).
        """
        try:
            # Try to find existing user by id
            resp = self.client.table('User').select("id, email, name").eq('id', user_id).execute()
            if resp.data:
                return resp.data[0]

            # Insert new user (email is required by schema)
            insert_payload = {
                'id': user_id,
                'email': email,
            }
            if name:
                insert_payload['name'] = name

            created = self.client.table('User').upsert(
                insert_payload,
                on_conflict='id'
            ).execute()
            return created.data[0] if created.data else {'id': user_id, 'email': email, 'name': name}
        except Exception as e:
            print(f"Error ensuring user exists: {str(e)}")
            raise

    # ---------------------- Projects ----------------------
    def create_project(self, project_data: dict) -> dict:
        """Create a new project in the database"""
        try:
            response = self.client.table('Project').insert(project_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating project: {str(e)}")
            raise

    def get_project_by_id(self, project_id: str) -> dict:
        """Get a project by its ID"""
        try:
            response = self.client.table('Project').select("*").eq('id', project_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error fetching project: {str(e)}")
            raise

    def get_projects_by_user_id(self, user_id: str) -> list:
        """Get all projects for a specific user"""
        try:
            response = self.client.table('Project').select("*").eq('userId', user_id).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching user projects: {str(e)}")
            raise

    def update_project_status(self, project_id: str, status: str) -> dict:
        """Update project upload status"""
        try:
            response = self.client.table('Project').update({
                'uploadStatus': status
            }).eq('id', project_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating project status: {str(e)}")
            raise

    def update_project_blob_keys(self, project_id: str, blob_keys: list) -> dict:
        """Update project blob keys"""
        try:
            response = self.client.table('Project').update({
                'blobKeys': blob_keys
            }).eq('id', project_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating project blob keys: {str(e)}")
            raise

    def get_project_by_collection_name(self, collection_name: str) -> dict:
        """Get project by collection name (unique)"""
        try:
            response = self.client.table('Project').select("*").eq('collectionName', collection_name).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error fetching project by collection name: {str(e)}")
            raise

    def update_project_summary_and_faq(self, project_id: str, summary: str, faq: list) -> dict:
        """Update project's summary and faq fields"""
        try:
            # Since faq column is now Json type, we can send the list directly
            # Supabase will handle the JSON serialization
            print(f"Storing FAQ list with {len(faq)} items")
            response = self.client.table('Project').update({
                'summary': summary,
                'faq': faq,  # Direct list, no need to json.dumps()
            }).eq('id', project_id).execute()
            stored_data = response.data[0] if response.data else None
            if stored_data:
                print(f"Successfully stored FAQ. Stored count: {len(stored_data.get('faq', []))}")
            return stored_data
        except Exception as e:
            print(f"Error updating project summary/faq: {str(e)}")
            raise

    def delete_project_by_collection_name(self, collection_name: str) -> dict:
        """Delete a project row by its unique collectionName and return the deleted row if available."""
        try:
            # Some Supabase versions support .delete().eq(...).select("*") to return deleted row
            response = self.client.table('Project').delete().eq('collectionName', collection_name).execute()
            # response.data may contain deleted rows depending on RLS/returning settings
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error deleting project by collection name: {str(e)}")
            raise

    # ---------------------- Chat ----------------------
    def create_chat(self, chat_data: dict) -> dict:
        """Create a new chat session"""
        try:
            response = self.client.table('Chat').insert(chat_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating chat: {str(e)}")
            raise

    def update_chat_messages(self, chat_id: str, messages: list) -> dict:
        """Update chat messages"""
        try:
            response = self.client.table('Chat').update({
                'messages': messages
            }).eq('id', chat_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating chat messages: {str(e)}")
            raise

    def get_chat_history(self, project_id: str, user_id: str) -> list:
        """Get chat history for a project and user"""
        try:
            response = self.client.table('Chat').select("*").eq('projectId', project_id).eq('userId', user_id).execute()
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching chat history: {str(e)}")
            raise

    # ---------------------- Sessions ----------------------
    def create_session(self, session_data: dict) -> dict:
        """Create a new Session record"""
        try:
            response = self.client.table('Session').insert(session_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error creating session: {str(e)}")
            raise

    def get_session(self, session_id: str) -> dict:
        """Fetch a Session by id"""
        try:
            response = self.client.table('Session').select('*').eq('id', session_id).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error fetching session: {str(e)}")
            raise

    # ---------------------- Chat helpers ----------------------
    def get_chat_by_session(self, session_id: str) -> dict:
        """Fetch Chat row tied to a Session"""
        try:
            response = self.client.table('Chat').select('*').eq('sessionId', session_id).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error fetching chat by session: {str(e)}")
            raise

    def update_chat_messages_by_session(self, session_id: str, messages: list) -> dict:
        """Update Chat messages for a given session id"""
        try:
            response = self.client.table('Chat').update({'messages': messages}).eq('sessionId', session_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating chat messages by session: {str(e)}")
            raise

    def update_chat_messages_by_chat(self, chat_id: str, messages: list) -> dict:
        """Update Chat messages for a given chat id"""
        try:
            response = self.client.table('Chat').update({'messages': messages}).eq('id', chat_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error updating chat messages by chat id: {str(e)}")
            raise

    def create_or_get_chat_for_session(self, session_id: str, project_id: str, user_id: str) -> dict:
        """Create a new chat for a session if it doesn't exist, otherwise return existing one"""
        try:
            # First check if chat already exists
            existing_chat = self.get_chat_by_session(session_id)
            if existing_chat:
                return existing_chat
            
            # Create new chat if none exists
            chat_id = cuid.cuid()
            chat_data = {
                "id": chat_id,
                "sessionId": session_id,
                "projectId": project_id,
                "userId": user_id,
                "messages": [],
                "createdAt": "NOW()",
                "updatedAt": "NOW()",
            }
            return self.create_chat(chat_data)
        except Exception as e:
            print(f"Error creating or getting chat for session: {str(e)}")
            raise


# Create global instance
supabase_client = SupabaseClient()