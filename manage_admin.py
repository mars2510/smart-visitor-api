import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.models.user import User


async def create_admin():
    async with AsyncSessionLocal() as db:
        username_admin = "admin"
        password_admin = "admin123"

        result = await db.execute(select(User).where(User.user_name == username_admin))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"User '{username_admin}' sudah ada di database.")
            return

        admin = User(
            nama="Administrator",
            peran="admin",
            password=get_password_hash(password_admin),
            user_name=username_admin,
        )
        db.add(admin)
        await db.commit()
        print(f"Berhasil membuat admin! Username: {username_admin} | Password: {password_admin}")


if __name__ == "__main__":
    asyncio.run(create_admin())
