from config.settings import settings

# JWT configuration using centralized settings
class JWTConfig:
    @property
    def JWT_SECRET(self) -> str:
        return settings.JWT_SECRET
    
    @property
    def JWT_ALGORITHM(self) -> str:
        return settings.JWT_ALGORITHM
    
    @property
    def JWT_EXPIRATION_HOURS(self) -> int:
        return settings.JWT_EXPIRATION_HOURS

jwt_config = JWTConfig()