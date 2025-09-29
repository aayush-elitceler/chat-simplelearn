import os
import uuid
from datetime import datetime
from typing import Dict, Optional
from fastapi import UploadFile, HTTPException
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError
from config.settings import settings
import mimetypes

class GCSUploadService:
    def __init__(self):
        """Initialize GCS client with credentials"""
        try:
            # Set credentials path if provided
            if settings.GCS_CREDENTIALS_PATH:
                # Check if file exists and is a file (not directory)
                if os.path.exists(settings.GCS_CREDENTIALS_PATH) and os.path.isfile(settings.GCS_CREDENTIALS_PATH):
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GCS_CREDENTIALS_PATH
                    print(f"Using GCS credentials from file: {settings.GCS_CREDENTIALS_PATH}")
                    
                    # Verify the credentials file is readable and valid JSON
                    try:
                        import json
                        with open(settings.GCS_CREDENTIALS_PATH, 'r') as f:
                            creds_data = json.load(f)
                        print(f"Credentials file validated - project_id: {creds_data.get('project_id', 'N/A')}")
                    except Exception as e:
                        print(f"Warning: Could not validate credentials file: {str(e)}")
                        
                else:
                    print(f"Warning: GCS credentials file not found or is not a file at {settings.GCS_CREDENTIALS_PATH}")
                    # Try alternative locations
                    alternative_paths = [
                        "/app/noui-2-d7968ae1b27d.json",
                        "/app/credentials/noui-2-d7968ae1b27d.json",
                        "./noui-2-d7968ae1b27d.json"
                    ]
                    
                    for alt_path in alternative_paths:
                        if os.path.exists(alt_path) and os.path.isfile(alt_path):
                            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = alt_path
                            print(f"Using GCS credentials from alternative path: {alt_path}")
                            break
                    else:
                        print("No valid GCS credentials file found in any location")
            
            # Initialize client
            if settings.GCS_PROJECT_ID:
                self.client = storage.Client(project=settings.GCS_PROJECT_ID)
                print(f"Initialized GCS client with project: {settings.GCS_PROJECT_ID}")
            else:
                self.client = storage.Client()
                print("Initialized GCS client without project ID")
            
            self.bucket_name = settings.GCS_BUCKET_NAME
            
            if not self.bucket_name:
                print("Warning: GCS_BUCKET_NAME is not configured")
                self.bucket_name = None
            else:
                print(f"Using GCS bucket: {self.bucket_name}")
                
                # Test bucket access
                try:
                    bucket = self.client.bucket(self.bucket_name)
                    # Try to get bucket metadata to verify access
                    bucket.reload()
                    print(f"Successfully connected to GCS bucket: {self.bucket_name}")
                except Exception as e:
                    print(f"Warning: Could not access GCS bucket {self.bucket_name}: {str(e)}")
                
        except Exception as e:
            print(f"Warning: Failed to initialize GCS client: {str(e)}")
            self.client = None
            self.bucket_name = None
    
    def get_file_category(self, filename: str) -> str:
        """Determine file category based on extension"""
        extension = filename.lower().split('.')[-1] if '.' in filename else ''
        
        file_categories = {
            # Documents
            'pdf': 'documents',
            'doc': 'documents',
            'docx': 'documents',
            'txt': 'documents',
            'rtf': 'documents',
            
            # Spreadsheets
            'xlsx': 'spreadsheets',
            'xls': 'spreadsheets',
            'csv': 'spreadsheets',
            
            # Presentations
            'ppt': 'presentations',
            'pptx': 'presentations',
            
            # Images
            'jpg': 'images',
            'jpeg': 'images',
            'png': 'images',
            'gif': 'images',
            'bmp': 'images',
            'svg': 'images',
            
            # Archives
            'zip': 'archives',
            'rar': 'archives',
            '7z': 'archives',
            'tar': 'archives',
            'gz': 'archives',
            
            # Videos
            'mp4': 'videos',
            'avi': 'videos',
            'mov': 'videos',
            'wmv': 'videos',
            'flv': 'videos',
            
            # Audio
            'mp3': 'audio',
            'wav': 'audio',
            'flac': 'audio',
            'aac': 'audio',
        }
        
        return file_categories.get(extension, 'others')
    
    def validate_file(self, file: UploadFile) -> bool:
        """Validate file size and type"""
        # Check file size (limit to 50MB)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
        
        if file.size and file.size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File size exceeds 50MB limit"
            )
        
        # Check if filename is provided
        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="Filename is required"
            )
        
        # Check for malicious file extensions
        dangerous_extensions = ['exe', 'bat', 'cmd', 'scr', 'pif', 'com']
        extension = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        
        if extension in dangerous_extensions:
            raise HTTPException(
                status_code=400,
                detail="File type not allowed for security reasons"
            )
        
        return True
    
    def generate_unique_filename(self, original_filename: str, user_id: str) -> str:
        """Generate a unique filename to prevent conflicts"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        
        # Extract file extension
        if '.' in original_filename:
            name, extension = original_filename.rsplit('.', 1)
            return f"{name}_{timestamp}_{unique_id}.{extension}"
        else:
            return f"{original_filename}_{timestamp}_{unique_id}"
    
    async def upload_file(self, file: UploadFile, user_id: str, collection_name: str) -> Dict[str, str]:
        """
        Upload file to GCS with organized folder structure
        
        Folder structure: users/{user_id}/{collection_name}/{category}/{year}/{month}/filename
        """
        # Check if GCS is properly configured
        if not self.client or not self.bucket_name:
            raise HTTPException(
                status_code=503,
                detail="Google Cloud Storage is not properly configured. Please check your environment variables and credentials file."
            )
        
        try:
            # Validate the file
            self.validate_file(file)
            
            # Get file category
            category = self.get_file_category(file.filename)
            
            # Generate unique filename
            unique_filename = self.generate_unique_filename(file.filename, user_id)
            
            # Create folder structure
            now = datetime.now()
            year = now.strftime("%Y")
            month = now.strftime("%m")
            
            # Construct blob path with collection_id
            blob_path = f"users/{user_id}/{collection_name}/{category}/{year}/{month}/{unique_filename}"
            
            # Get bucket
            bucket = self.client.bucket(self.bucket_name)
            blob = bucket.blob(blob_path)
            
            # Set metadata
            metadata = {
                'uploaded_by': user_id,
                'collection_name': collection_name,
                'original_filename': file.filename,
                'category': category,
                'upload_timestamp': now.isoformat(),
                'content_type': file.content_type or mimetypes.guess_type(file.filename)[0]
            }
            blob.metadata = metadata
            
            # Upload file
            file.file.seek(0)  # Reset file pointer
            blob.upload_from_file(
                file.file,
                content_type=file.content_type or mimetypes.guess_type(file.filename)[0]
            )
            
            return {
                "success": True,
                "message": "File uploaded successfully",
                "file_info": {
                    "original_filename": file.filename,
                    "stored_filename": unique_filename,
                    "category": category,
                    "blob_path": blob_path,
                    "size": file.size,
                    "content_type": file.content_type,
                    "upload_timestamp": now.isoformat(),
                    "public_url": blob.public_url,
                    "collection_name": collection_name
                }
            }
            
        except GoogleCloudError as e:
            print(f"GCS Error during upload: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Google Cloud Storage error: {str(e)}"
            )
        except Exception as e:
            print(f"Unexpected error during upload: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"File upload failed: {str(e)}"
            )

# Create global instance
gcs_upload_service = GCSUploadService()