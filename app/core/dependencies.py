from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

# Fungsi untuk mengambil user dari Token (Header atau Cookie)
async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sesi berakhir, silakan login kembali",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Coba ambil token dari Header (untuk API/Mobile)
    final_token = token
    
    # 2. Jika tidak ada di Header, coba ambil dari Cookie (untuk Web Admin)
    if not final_token:
        final_token = request.cookies.get("access_token")

    if not final_token:
        raise credentials_exception

    try:
        payload = jwt.decode(final_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    result = await db.execute(select(User).where(User.user_name == username))
    user = result.scalars().first()
    if user is None:
        raise credentials_exception
    return user

# Fungsi khusus untuk memvalidasi apakah user adalah Admin
async def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.peran != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak. Anda bukan Admin."
        )
    return current_user