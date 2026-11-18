# app/repositories/mitra_repo.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.visitor import MitraPerusahaan

class MitraRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, q: str = None):
        query = select(MitraPerusahaan)
        if q: query = query.where(MitraPerusahaan.nama_perusahaan.ilike(f"%{q}%"))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, id_perusahaan: int):
        result = await self.db.execute(select(MitraPerusahaan).where(MitraPerusahaan.id_perusahaan == id_perusahaan))
        return result.scalars().first()

    async def create(self, mitra: MitraPerusahaan):
        self.db.add(mitra)
        await self.db.flush()
        return mitra

    async def update(self, mitra: MitraPerusahaan):
        await self.db.flush()
        return mitra

    async def delete(self, mitra: MitraPerusahaan):
        await self.db.delete(mitra)