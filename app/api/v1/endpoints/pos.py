# app/api/v1/endpoints/pos.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.config import settings
from app.core.database import get_db
from app.models.visitor import Pos
from app.repositories.pos_repo import PosRepository
from app.schemas.pos_schema import PosCreate, PosUpdate, PosResponse

router = APIRouter()

@router.get("/all", response_model=List[PosResponse])
async def get_all_pos(q: str = Query(None), db: AsyncSession = Depends(get_db)):
    repo = PosRepository(db)
    return await repo.get_all(q)

@router.get("/destinations", response_model=List[PosResponse])
async def get_destination_pos(
    q: str = Query(None), db: AsyncSession = Depends(get_db)
):
    query = select(Pos).where(Pos.id_pos != settings.MAIN_POS_ID)
    if q:
        query = query.where(Pos.nama_pos.ilike(f"%{q}%"))
    result = await db.execute(query.order_by(Pos.id_pos))
    return result.scalars().all()

@router.post("/create", response_model=PosResponse)
async def create_pos(data: PosCreate, db: AsyncSession = Depends(get_db)):
    repo = PosRepository(db)
    new_pos = Pos(nama_pos=data.nama_pos)
    await repo.create(new_pos)
    await db.commit()
    await db.refresh(new_pos)
    return new_pos

@router.put("/update/{id_pos}", response_model=PosResponse)
async def update_pos(id_pos: int, data: PosUpdate, db: AsyncSession = Depends(get_db)):
    repo = PosRepository(db)
    pos = await repo.get_by_id(id_pos)
    if not pos:
        raise HTTPException(status_code=404, detail="POS tidak ditemukan")
    
    if data.nama_pos: pos.nama_pos = data.nama_pos
    await repo.update(pos)
    await db.commit()
    await db.refresh(pos)
    return pos

@router.delete("/delete/{id_pos}")
async def delete_pos(id_pos: int, db: AsyncSession = Depends(get_db)):
    repo = PosRepository(db)
    pos = await repo.get_by_id(id_pos)
    if not pos:
        raise HTTPException(status_code=404, detail="POS tidak ditemukan")
    
    await repo.delete(pos)
    await db.commit()
    return {"message": "POS berhasil dihapus"}