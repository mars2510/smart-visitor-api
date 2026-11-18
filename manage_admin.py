import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.user import User  # Sesuaikan path model User Anda
from app.core.security import get_password_hash  # Sesuaikan fungsi hash password Anda

async def create_admin():
    async with AsyncSessionLocal() as db:
        username_admin = "admin"
        password_admin = "admin123"

        # Cek apakah user sudah ada agar aman dijalankan berulang kali
        result = await db.execute(select(User).where(User.username == username_admin))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"User '{username_admin}' sudah ada di database.")
            return

        admin = User(
            username=username_admin,
            # email="admin@example.com",  # Aktifkan jika model User butuh kolom email
            # nama="Administrator",       # Aktifkan jika model User butuh kolom nama
            hashed_password=get_password_hash(password_admin),  # Sesuaikan nama kolom password
            role="admin",  # Sesuaikan role/is_superuser di model User Anda
            is_active=True
        )
        db.add(admin)
        await db.commit()
        print(f"Berhasil membuat admin! Username: {username_admin} | Password: {password_admin}")

if __name__ == "__main__":
    asyncio.run(create_admin())
