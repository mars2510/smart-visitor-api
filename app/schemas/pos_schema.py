# app/schemas/pos_schema.py
from pydantic import BaseModel
from typing import Optional

class PosCreate(BaseModel):
    nama_pos: str

class PosUpdate(BaseModel):
    nama_pos: Optional[str] = None

class PosResponse(BaseModel):
    id_pos: int
    nama_pos: str

    class Config:
        from_attributes = True