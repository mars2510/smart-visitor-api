from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.visit import Visit, VisitDestination
from app.models.visitor import Visitor, Vehicle

class VisitRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_visitor_by_name_phone(self, nama: str, telepon: str):
        result = await self.db.execute(select(Visitor).where(Visitor.nama == nama, Visitor.telepon == telepon))
        return result.scalars().first()

    async def create_visitor(self, visitor: Visitor):
        self.db.add(visitor)
        await self.db.flush()
        return visitor

    async def get_vehicle_by_plate(self, nomor_polisi: str):
        result = await self.db.execute(select(Vehicle).where(Vehicle.nomor_polisi == nomor_polisi))
        return result.scalars().first()

    async def create_vehicle(self, vehicle: Vehicle):
        self.db.add(vehicle)
        await self.db.flush()
        return vehicle

    async def create_visit(self, visit: Visit):
        self.db.add(visit)
        await self.db.flush()
        return visit

    async def create_destination(self, dest: VisitDestination):
        self.db.add(dest)
        await self.db.flush()

    async def get_visit_by_qr(self, kode_qr: str):
        result = await self.db.execute(select(Visit).where(Visit.kode_qr == kode_qr))
        return result.scalars().first()