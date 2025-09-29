from typing import List, Dict, Any, Optional
from datetime import datetime
from models.project import Project, UploadStatus
from services.supabase_client import supabase_client
from utility.response import create_error_response
from services.gcs_upload_service import gcs_upload_service
from repository.rags.rags_repo import rags_repo
from repository.general_utilities.general_utility_repo import general_utility_repo

class ProjectService:
    """Service layer for project-related operations"""
    
    def __init__(self):
        self.supabase_client = supabase_client
    
    def get_user_projects(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all projects for a specific user
        
        Args:
            user_id: ID of the user
            
        Returns:
            List of project dictionaries
        """
        try:
            projects = self.supabase_client.get_projects_by_user_id(user_id)
            return self._format_projects_data(projects)
        except Exception as e:
            print(f"Error fetching user projects: {str(e)}")
            raise
    
    def get_project_by_id(self, project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific project by ID with user authorization
        
        Args:
            project_id: ID of the project
            user_id: ID of the user requesting the project
            
        Returns:
            Project dictionary if found and authorized, None otherwise
        """
        try:
            project = self.supabase_client.get_project_by_id(project_id)
            if not project:
                return None
            
            # Check if user is authorized to access this project
            if project.get("userId") != user_id:
                return None
            
            return self._format_single_project_data(project)
        except Exception as e:
            print(f"Error fetching project: {str(e)}")
            raise
    
    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new project
        
        Args:
            project_data: Project data dictionary
            
        Returns:
            Created project dictionary
        """
        try:
            project = self.supabase_client.create_project(project_data)
            return self._format_single_project_data(project)
        except Exception as e:
            print(f"Error creating project: {str(e)}")
            raise
    
    def update_project_status(self, project_id: str, status: UploadStatus) -> Optional[Dict[str, Any]]:
        """
        Update project upload status
        
        Args:
            project_id: ID of the project
            status: New upload status
            
        Returns:
            Updated project dictionary
        """
        try:
            project = self.supabase_client.update_project_status(project_id, status)
            return self._format_single_project_data(project) if project else None
        except Exception as e:
            print(f"Error updating project status: {str(e)}")
            raise
    
    def update_project_blob_keys(self, project_id: str, blob_keys: List[str]) -> Optional[Dict[str, Any]]:
        """
        Update project blob keys
        
        Args:
            project_id: ID of the project
            blob_keys: List of blob keys
            
        Returns:
            Updated project dictionary
        """
        try:
            project = self.supabase_client.update_project_blob_keys(project_id, blob_keys)
            return self._format_single_project_data(project) if project else None
        except Exception as e:
            print(f"Error updating project blob keys: {str(e)}")
            raise
    
    def get_project_by_collection_name(self, collection_name: str) -> Optional[Dict[str, Any]]:
        """
        Get project by collection name
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Project dictionary if found, None otherwise
        """
        try:
            project = self.supabase_client.get_project_by_collection_name(collection_name)
            return self._format_single_project_data(project) if project else None
        except Exception as e:
            print(f"Error fetching project by collection name: {str(e)}")
            raise
    
    def _format_projects_data(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format list of projects data
        
        Args:
            projects: Raw projects data from database
            
        Returns:
            Formatted projects data
        """
        formatted_projects = []
        
        for project in projects:
            try:
                formatted_project = self._format_single_project_data(project)
                if formatted_project:
                    formatted_projects.append(formatted_project)
            except Exception as e:
                print(f"Error formatting project {project.get('id', 'unknown')}: {str(e)}")
                continue
        
        return formatted_projects
    
    def _format_single_project_data(self, project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Format single project data
        
        Args:
            project: Raw project data from database
            
        Returns:
            Formatted project data or None if invalid
        """
        try:
            # Validate required fields
            required_fields = ["id", "name", "userId", "collectionName"]
            if not all(project.get(field) for field in required_fields):
                print(f"Project missing required fields: {project}")
                return None
            
            blob_keys: List[str] = project.get("blobKeys", []) or []

            # Build public URLs safely
            file_urls: List[str] = []
            try:
                if gcs_upload_service.client and gcs_upload_service.bucket_name:
                    bucket = gcs_upload_service.client.bucket(gcs_upload_service.bucket_name)
                    for blob_path in blob_keys:
                        try:
                            blob = bucket.blob(blob_path)
                            file_urls.append(blob.public_url)
                        except Exception as e:
                            print(f"Failed to construct GCS URL for {blob_path}: {e}")
                            continue
            except Exception as e:
                print(f"GCS client/bucket not available: {e}")

            # Compute document size stats from vector store documents (best-effort)
            # doc_size_stats: Dict[str, Any] = {}
            # try:
            #     collection_name = project.get("collectionName")
            #     if collection_name:
            #         docs = rags_repo.get_collection_documents(collection_name, max_docs=2000)
            #         doc_size_stats = general_utility_repo.calculate_documents_size(docs)
            # except Exception as e:
            #     print(f"Failed to compute document size stats: {e}")
            #     doc_size_stats = {}

            # Compute storage size stats directly from GCS blobs (authoritative for uploaded files)
            storage_size_stats: Dict[str, Any] = {}
            try:
                total_bytes = 0
                files_meta: List[Dict[str, Any]] = []
                if gcs_upload_service.client and gcs_upload_service.bucket_name:
                    bucket = gcs_upload_service.client.bucket(gcs_upload_service.bucket_name)
                    for blob_path in blob_keys:
                        try:
                            blob = bucket.blob(blob_path)
                            blob.reload()  # Ensure metadata is loaded
                            size_bytes = int(getattr(blob, 'size', 0) or 0)
                            total_bytes += size_bytes
                            files_meta.append({
                                "filename": blob_path.split("/")[-1],
                                "blobKey": blob_path,
                                "size_bytes": size_bytes,
                                "size_mb": round(size_bytes / (1024 * 1024), 2),
                                "url": blob.public_url,
                            })
                        except Exception as e:
                            print(f"Failed to read size for {blob_path}: {e}")
                            continue
                storage_size_stats = {
                    # "total_size_bytes": total_bytes,
                    # "total_size_mb": round(total_bytes / (1024 * 1024), 2),
                    "total_size_formatted": f"{(total_bytes / (1024 * 1024)):.2f} MB",
                    # "file_count": len(files_meta),
                    # "files": files_meta,
                }
            except Exception as e:
                print(f"Failed to compute storage size stats: {e}")
                storage_size_stats = {}

            # # Prefer storage size stats if document-derived stats are empty
            # effective_size_stats = doc_size_stats
            # try:
            #     if not effective_size_stats or effective_size_stats.get("document_count", 0) == 0:
            #         effective_size_stats = storage_size_stats
            # except Exception:
            #     effective_size_stats = storage_size_stats

            # Format the project data
            formatted_project = {
                "id": project.get("id"),
                "name": project.get("name"),
                "userId": project.get("userId"),
                "collectionName": project.get("collectionName"),
                "description": project.get("description"),
                "projectId": project.get("projectId") or project.get("collectionName"),
                "uploadStatus": project.get("uploadStatus", UploadStatus.PENDING),
                "blobKeys": blob_keys,
                "documentCount": len(blob_keys),
                "fileUrls": file_urls,
                "summary": project.get("summary"),
                "faq": project.get("faq", []),
                # "documentSize": effective_size_stats,
                "storageSize": storage_size_stats,
                "createdAt": self._format_datetime(project.get("createdAt")),
                "updatedAt": self._format_datetime(project.get("updatedAt"))
            }
            
            return formatted_project
            
        except Exception as e:
            print(f"Error formatting project data: {str(e)}")
            return None
    
    def _format_datetime(self, datetime_value: Any) -> str:
        """
        Format datetime to ISO 8601 string
        
        Args:
            datetime_value: Datetime value (can be string, datetime object, or None)
            
        Returns:
            ISO 8601 formatted datetime string
        """
        if not datetime_value:
            return datetime.now().isoformat()
        
        if isinstance(datetime_value, str):
            try:
                # Try to parse and reformat
                dt = datetime.fromisoformat(datetime_value.replace('Z', '+00:00'))
                return dt.isoformat()
            except ValueError:
                try:
                    dt = datetime.fromisoformat(datetime_value)
                    return dt.isoformat()
                except ValueError:
                    return datetime.now().isoformat()
        
        if isinstance(datetime_value, datetime):
            return datetime_value.isoformat()
        
        return datetime.now().isoformat()

# Create global instance
project_service = ProjectService()
