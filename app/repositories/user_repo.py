# app/repositories/user_repo.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import User

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self):
        result = await self.db.execute(select(User))
        return result.scalars().all()

    async def get_by_id(self, user_id: int):
        result = await self.db.execute(select(User).where(User.id_pengguna == user_id))
        return result.scalars().first()

    async def get_by_username(self, username: str):
        result = await self.db.execute(select(User).where(User.user_name == username))
        return result.scalars().first()

    async def create(self, user: User):
        self.db.add(user)
        await self.db.flush()
        return user

    async def update(self, user: User):
        await self.db.flush()
        return user

    async def delete(self, user: User):
        await self.db.delete(user)