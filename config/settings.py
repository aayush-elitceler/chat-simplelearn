import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Centralized configuration for the entire application.
    All environment variables should be defined here.
    """
    
    # Application Settings
    APP_NAME: str = "NOUI API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "A secure API with JWT authentication middleware"
    DEBUG: bool = False
    
    # Server Settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # JWT Settings
    JWT_SECRET: str
    JWT_ALGORITHM: str
    JWT_EXPIRATION_HOURS: int

    # Google Cloud Storage Settings
    GCS_BUCKET_NAME: Optional[str] = None
    GCS_CREDENTIALS_PATH: Optional[str] = None
    GCS_PROJECT_ID: Optional[str] = None

    # Supabase settings
    SUPABASE_URL: str
    SUPABASE_KEY: str

    # Security Settings
    CORS_ORIGINS: str = "*" 
    ALLOWED_HOSTS: str = "*" 
    
    # Logging Settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    MILVUS_URI: str = Field(..., env="MILVUS_URI")
    MILVUS_TOKEN: str = Field(..., env="MILVUS_TOKEN")
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
    
    @property
    def cors_origins_list(self) -> list:
        """Convert CORS_ORIGINS string to list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    @property
    def allowed_hosts_list(self) -> list:
        """Convert ALLOWED_HOSTS string to list"""
        if self.ALLOWED_HOSTS == "*":
            return ["*"]
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",")]

# Create a global settings instance
settings = Settings()

# Function to get settings (useful for dependency injection)
def get_settings() -> Settings:
    return settings 