from .file_process_router import router as file_processing_router
from .rag_router import router as rag_router
from .general_utility_router import router as general_utility_router
# from .protected_routes import router as protected_router

# List of all routers to be included in the main app
__all__ = [
    "file_processing_router",
    "rag_router",
    "general_utility_router",
    # "protected_router"
]