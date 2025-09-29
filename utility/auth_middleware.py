from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from datetime import datetime
from models.user import UserData
from config.settings import settings

# Security scheme for Bearer token
security = HTTPBearer()

class AuthMiddleware:
    def __init__(self, jwt_secret: str):
        self.jwt_secret = jwt_secret

    async def __call__(self, request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserData:
        try:
            # Extract token from Authorization header
            token = credentials.credentials
            
            # Debug: Print JWT secret (remove in production)
            print(f"Debug: JWT Secret length: {len(self.jwt_secret) if self.jwt_secret else 0}")
            print(f"Debug: JWT Algorithm: {settings.JWT_ALGORITHM}")
            
            # Decode JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=[settings.JWT_ALGORITHM])
            
            # Check if token is expired
            current_time = datetime.utcnow().timestamp()
            if payload.get("exp") and payload["exp"] < current_time:
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired"
                )
            
            # Create UserData object based on actual token claims
            user_data = UserData(
                id=payload["id"],
                email=payload["email"],
                name=payload["name"],
                iat=payload["iat"],
                exp=payload["exp"]
            )
            
            # Store user data in request state for later use
            request.state.user = user_data
            
            return user_data
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        except KeyError as e:
            raise HTTPException(
                status_code=401,
                detail=f"Missing required field in token: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=401,
                detail=f"Authentication failed: {str(e)}"
            )

# Initialize the auth middleware
auth_middleware = AuthMiddleware(jwt_secret=settings.JWT_SECRET) 