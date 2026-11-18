# app/services/pos_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.pos_repo import PosRepository
from app.models.visitor import Pos

class PosService:
    def __init__(self, db: AsyncSession):
        self.repo = PosRepository(db)
        self.db = db

    async def add_pos(self, nama_pos: str):
        # Opsional: Cek duplikasi nama pos
        existing_pos = await self.repo.get_all_pos(q=nama_pos)
        if any(p.nama_pos.lower() == nama_pos.lower() for p in existing_pos):
            raise ValueError(f"POS dengan nama '{nama_pos}' sudah ada.")
            
        new_pos = Pos(nama_pos=nama_pos)
        await self.repo.create_pos(new_pos)
        await self.db.commit()
        await self.db.refresh(new_pos)
        return new_pos

    async def list_pos(self, q: str = None):
        return await self.repo.get_all_pos(q)