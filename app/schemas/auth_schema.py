from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class UserLogin(BaseModel):
    username: str
    password: str

# app/schemas/auth_schema.py
from pydantic import BaseModel
from typing import Optional

class UserBase(BaseModel):
    nama: str
    user_name: str
    peran: str # admin, security, user

class UserCreate(UserBase):
    password: str
    id_pos: Optional[int] = None

class UserUpdate(BaseModel):
    nama: Optional[str] = None
    peran: Optional[str] = None
    password: Optional[str] = None
    id_pos: Optional[int] = None

class UserResponse(UserBase):
    id_pengguna: int
    id_pos: Optional[int] = None

    class Config:
        from_attributes = True