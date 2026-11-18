# app/api/v1/endpoints/mitra.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.models.visitor import MitraPerusahaan
from app.repositories.mitra_repo import MitraRepository
from app.schemas.mitra_schema import MitraCreate, MitraUpdate, MitraResponse

router = APIRouter()

@router.get("/all", response_model=List[MitraResponse])
async def get_all_mitra(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    repo = MitraRepository(db)
    return await repo.get_all(q)

@router.post("/create", response_model=MitraResponse)
async def create_mitra(data: MitraCreate, db: AsyncSession = Depends(get_db)):
    repo = MitraRepository(db)
    new_mitra = MitraPerusahaan(nama_perusahaan=data.nama_perusahaan)
    await repo.create(new_mitra)
    await db.commit()
    await db.refresh(new_mitra)
    return new_mitra

@router.put("/update/{id_perusahaan}", response_model=MitraResponse)
async def update_mitra(id_perusahaan: int, data: MitraUpdate, db: AsyncSession = Depends(get_db)):
    repo = MitraRepository(db)
    mitra = await repo.get_by_id(id_perusahaan)
    if not mitra:
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    
    if data.nama_perusahaan: mitra.nama_perusahaan = data.nama_perusahaan
    await repo.update(mitra)
    await db.commit()
    await db.refresh(mitra)
    return mitra

@router.delete("/delete/{id_perusahaan}")
async def delete_mitra(id_perusahaan: int, db: AsyncSession = Depends(get_db)):
    repo = MitraRepository(db)
    mitra = await repo.get_by_id(id_perusahaan)
    if not mitra:
        raise HTTPException(status_code=404, detail="Mitra tidak ditemukan")
    
    await repo.delete(mitra)
    await db.commit()
    return {"message": "Mitra berhasil dihapus"}