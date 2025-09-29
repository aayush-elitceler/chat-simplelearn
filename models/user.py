from pydantic import BaseModel

class UserData(BaseModel):
    id: str
    email: str
    name: str
    iat: int
    exp: int 