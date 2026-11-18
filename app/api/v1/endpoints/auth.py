from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.database import get_db
from app.core.config import settings
from app.core.dependencies import get_current_admin, get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.models.visitor import Pos
from app.repositories.user_repo import UserRepository
from app.schemas.auth_schema import Token, UserCreate, UserResponse, UserUpdate

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            (User.user_name == form_data.username) | (User.email == form_data.username)
        )
    )
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
        )

    access_token = create_access_token(
        data={"sub": user.user_name, "role": user.peran}
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_current_user_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pos = await db.get(Pos, user.id_pos) if user.id_pos is not None else None
    return {
        "id_pengguna": user.id_pengguna,
        "nama": user.nama,
        "user_name": user.user_name,
        "peran": user.peran,
        "id_pos": user.id_pos,
        "nama_pos": pos.nama_pos if pos else None,
        "is_pos_utama": user.id_pos == settings.MAIN_POS_ID,
    }


@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    return await UserRepository(db).get_all()


@router.post("/users", response_model=UserResponse)
async def create_user(
    data: UserCreate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    if await repo.get_by_username(data.user_name):
        raise HTTPException(status_code=400, detail="Username sudah digunakan")
    if data.peran == "security" and data.id_pos is None:
        raise HTTPException(
            status_code=400, detail="Akun security wajib ditautkan ke pos"
        )
    if data.id_pos is not None and await db.get(Pos, data.id_pos) is None:
        raise HTTPException(status_code=400, detail="POS tidak ditemukan")

    new_user = User(
        nama=data.nama,
        user_name=data.user_name,
        peran=data.peran,
        password=get_password_hash(data.password),
        id_pos=data.id_pos,
    )
    await repo.create(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    data: UserUpdate,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    updates = data.model_dump(exclude_unset=True)
    if "id_pos" in updates:
        if updates["id_pos"] is not None and await db.get(Pos, updates["id_pos"]) is None:
            raise HTTPException(status_code=400, detail="POS tidak ditemukan")
        user.id_pos = updates["id_pos"]
    if updates.get("nama"):
        user.nama = updates["nama"]
    if updates.get("peran"):
        user.peran = updates["peran"]
    if updates.get("password"):
        user.password = get_password_hash(updates["password"])
    if user.peran == "security" and user.id_pos is None:
        raise HTTPException(
            status_code=400, detail="Akun security wajib ditautkan ke pos"
        )

    await repo.update(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")

    await repo.delete(user)
    await db.commit()
    return {"message": "User berhasil dihapus"}
