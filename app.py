from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.protected_routes import router as protected_router
from config.settings import settings
from services.gcs_upload_service import gcs_upload_service
from routers.file_process_router import router as file_processing_router
from routers.rag_router import router as rag_router
from routers.general_utility_router import router as general_utility_router

app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# Add CORS middleware for localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include protected routes
app.include_router(protected_router)
app.include_router(file_processing_router)
app.include_router(rag_router)
app.include_router(general_utility_router)

@app.get("/")
async def root():
    """
    Root endpoint - Public endpoint (no authentication required)
    """
    return {"message": "Welcome", "status": "running"}

@app.get("/health")
async def health_check():
    """
    Health check endpoint - Public endpoint (no authentication required)
    """
    return {"status": "healthy", "message": "API is running properly"}

@app.get("/gcs-health")
async def gcs_health_check():
    """
    GCS health check endpoint - Public endpoint (no authentication required)
    """
    try:
        # Check if GCS service is properly initialized
        if not gcs_upload_service.client or not gcs_upload_service.bucket_name:
            return {
                "status": "unhealthy",
                "message": "GCS service not properly initialized",
                "details": {
                    "client_initialized": gcs_upload_service.client is not None,
                    "bucket_name": gcs_upload_service.bucket_name
                }
            }
        
        # Test bucket access
        bucket = gcs_upload_service.client.bucket(gcs_upload_service.bucket_name)
        bucket.reload()  # This will fail if we don't have proper permissions
        
        return {
            "status": "healthy",
            "message": "GCS service is working properly",
            "details": {
                "bucket_name": gcs_upload_service.bucket_name,
                "project_id": settings.GCS_PROJECT_ID,
                "credentials_path": settings.GCS_CREDENTIALS_PATH,
                "credentials_valid": True
            }
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"GCS service error: {str(e)}",
            "details": {
                "bucket_name": gcs_upload_service.bucket_name,
                "project_id": settings.GCS_PROJECT_ID,
                "credentials_path": settings.GCS_CREDENTIALS_PATH,
                "error": str(e)
            }
        }

@app.get("/debug/env")
async def debug_environment():
    """
    Debug endpoint to check environment variables (remove in production)
    """
    import os
    return {
        "jwt_secret_length": len(settings.JWT_SECRET) if settings.JWT_SECRET else 0,
        "jwt_algorithm": settings.JWT_ALGORITHM,
        "gcs_bucket": settings.GCS_BUCKET_NAME,
        "gcs_project": settings.GCS_PROJECT_ID,
        "gcs_credentials_path": settings.GCS_CREDENTIALS_PATH,
        "gcs_credentials_exists": os.path.exists(settings.GCS_CREDENTIALS_PATH) if settings.GCS_CREDENTIALS_PATH else False,
        "gcs_credentials_isfile": os.path.isfile(settings.GCS_CREDENTIALS_PATH) if settings.GCS_CREDENTIALS_PATH else False,
        "gcs_client_initialized": gcs_upload_service.client is not None,
        "gcs_bucket_name": gcs_upload_service.bucket_name,
        "app_name": settings.APP_NAME,
        "debug_mode": settings.DEBUG
    }

