# app/schemas/mitra_schema.py
from pydantic import BaseModel
from typing import Optional

class MitraCreate(BaseModel):
    nama_perusahaan: str

class MitraUpdate(BaseModel):
    nama_perusahaan: Optional[str] = None

class MitraResponse(BaseModel):
    id_perusahaan: int
    nama_perusahaan: str

    class Config:
        from_attributes = True