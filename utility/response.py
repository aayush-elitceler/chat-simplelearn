from typing import Any, Dict, List, Optional, Union
from fastapi import status
from fastapi.responses import JSONResponse
from datetime import datetime
import json

class APIResponse:
    """Standardized API response wrapper"""
    
    def __init__(
        self,
        data: Any = None,
        message: str = "Success",
        status_code: int = status.HTTP_200_OK,
        success: bool = True
    ):
        self.data = data
        self.message = message
        self.status_code = status_code
        self.success = success
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary format"""
        return {
            "statusCode": self.status_code,
            "success": self.success,
            "message": self.message,
            "data": self.data
        }
    
    def to_json_response(self) -> JSONResponse:
        """Convert response to FastAPI JSONResponse"""
        return JSONResponse(
            content=self.to_dict(),
            status_code=self.status_code
        )

def create_success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = status.HTTP_200_OK
) -> Dict[str, Any]:
    """
    Create a standardized success response
    
    Args:
        data: Response data
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Standardized response dictionary
    """
    return APIResponse(
        data=data,
        message=message,
        status_code=status_code,
        success=True
    ).to_dict()

def create_error_response(
    message: str = "Error occurred",
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    data: Any = None
) -> Dict[str, Any]:
    """
    Create a standardized error response
    
    Args:
        message: Error message
        status_code: HTTP status code
        data: Additional error data
        
    Returns:
        Standardized error response dictionary
    """
    return APIResponse(
        data=data,
        message=message,
        status_code=status_code,
        success=False
    ).to_dict()

def create_list_response(
    items: List[Any],
    message: str = "Items fetched successfully",
    status_code: int = status.HTTP_200_OK
) -> Dict[str, Any]:
    """
    Create a standardized response for list data
    
    Args:
        items: List of items
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Standardized list response dictionary
    """
    return create_success_response(
        data=items,
        message=message,
        status_code=status_code
    )

def create_single_item_response(
    item: Any,
    message: str = "Item fetched successfully",
    status_code: int = status.HTTP_200_OK
) -> Dict[str, Any]:
    """
    Create a standardized response for single item data
    
    Args:
        item: Single item
        message: Success message
        status_code: HTTP status code
        
    Returns:
        Standardized single item response dictionary
    """
    return create_success_response(
        data=item,
        message=message,
        status_code=status_code
    )

def create_created_response(
    data: Any = None,
    message: str = "Resource created successfully"
) -> Dict[str, Any]:
    """Create a standardized response for resource creation"""
    return create_success_response(
        data=data,
        message=message,
        status_code=status.HTTP_201_CREATED
    )

def create_updated_response(
    data: Any = None,
    message: str = "Resource updated successfully"
) -> Dict[str, Any]:
    """Create a standardized response for resource updates"""
    return create_success_response(
        data=data,
        message=message,
        status_code=status.HTTP_200_OK
    )

def create_deleted_response(
    message: str = "Resource deleted successfully"
) -> Dict[str, Any]:
    """Create a standardized response for resource deletion"""
    return create_success_response(
        data=None,
        message=message,
        status_code=status.HTTP_200_OK
    )

def create_not_found_response(
    message: str = "Resource not found"
) -> Dict[str, Any]:
    """Create a standardized response for not found errors"""
    return create_error_response(
        message=message,
        status_code=status.HTTP_404_NOT_FOUND
    )

def create_validation_error_response(
    message: str = "Validation error",
    data: Any = None
) -> Dict[str, Any]:
    """Create a standardized response for validation errors"""
    return create_error_response(
        message=message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        data=data
    )

def create_unauthorized_response(
    message: str = "Unauthorized access"
) -> Dict[str, Any]:
    """Create a standardized response for unauthorized access"""
    return create_error_response(
        message=message,
        status_code=status.HTTP_401_UNAUTHORIZED
    )

def create_forbidden_response(
    message: str = "Access forbidden"
) -> Dict[str, Any]:
    """Create a standardized response for forbidden access"""
    return create_error_response(
        message=message,
        status_code=status.HTTP_403_FORBIDDEN
    )
