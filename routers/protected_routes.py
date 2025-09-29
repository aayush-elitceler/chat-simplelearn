from fastapi import APIRouter, Depends, Request, UploadFile, File, Form
from models.user import UserData
from utility.auth_middleware import auth_middleware
from services.gcs_upload_service import gcs_upload_service

router = APIRouter(prefix="/api/v1", tags=["protected"])

@router.get("/profile")
async def get_user_profile(
    request: Request,
    current_user: UserData = Depends(auth_middleware)
):
    """
    Get current user profile - Protected endpoint
    Requires valid Bearer token in Authorization header
    """
    return {
        "message": "User profile retrieved successfully",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name
        }
    }


@router.post("/upload-file")
async def upload_file_to_gcs(
    request: Request,
    file: UploadFile = File(...),
    project_id: str = Form(...),
    collection_name: str = Form(...),
    current_user: UserData = Depends(auth_middleware)
):
    """
    Upload file to Google Cloud Storage - Protected endpoint
    
    - Requires valid Bearer token in Authorization header
    - Organizes files by type (.xlsx -> spreadsheets/, .docx -> documents/, etc.)
    - Creates folder structure: users/{user_id}/{category}/{year}/{month}/filename
    - Validates file size (max 50MB) and type for security
    - Returns signed URL for secure file access
    
    Supported file categories:
    - Documents: pdf, doc, docx, txt, rtf
    - Spreadsheets: xlsx, xls, csv
    - Presentations: ppt, pptx
    - Images: jpg, jpeg, png, gif, bmp, svg
    - Archives: zip, rar, 7z, tar, gz
    - Videos: mp4, avi, mov, wmv, flv
    - Audio: mp3, wav, flac, aac
    - Others: any other file type
    """
    try:
        # Upload file using the GCS service
        result = await gcs_upload_service.upload_file(file, current_user.id, project_id, collection_name)
        
        return {
            "success": True,
            "message": f"File '{file.filename}' uploaded successfully by {current_user.name}",
            "uploaded_by": {
                "user_id": current_user.id,
                "name": current_user.name,
                "email": current_user.email
            },
            **result
        }
        
    except Exception as e:
        # The service already handles HTTPExceptions, so this catches any unexpected errors
        return {
            "success": False,
            "message": f"File upload failed: {str(e)}",
            "uploaded_by": {
                "user_id": current_user.id,
                "name": current_user.name
            }
        }

@router.post("/secure-action")
async def perform_secure_action(
    request: Request,
    current_user: UserData = Depends(auth_middleware)
):
    """
    Perform a secure action - Protected endpoint
    Requires valid Bearer token in Authorization header
    """
    return {
        "message": "Secure action performed successfully",
        "performed_by": current_user.name,
        "user_id": current_user.id
    } 