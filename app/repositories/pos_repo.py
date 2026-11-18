# app/repositories/pos_repo.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.visitor import Pos

class PosRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, q: str = None):
        query = select(Pos)
        if q: query = query.where(Pos.nama_pos.ilike(f"%{q}%"))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, id_pos: int):
        result = await self.db.execute(select(Pos).where(Pos.id_pos == id_pos))
        return result.scalars().first()

    async def create(self, pos: Pos):
        self.db.add(pos)
        await self.db.flush()
        return pos

    async def update(self, pos: Pos):
        await self.db.flush()
        return pos

    async def delete(self, pos: Pos):
        await self.db.delete(pos)