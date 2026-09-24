from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.deps import CurrentUser, DbDep
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut, ProfileUpdateIn
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

ALLOWED_ROLES = {"viewer", "creator", "advertiser"}


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, db: DbDep) -> TokenOut:
    role = payload.role if payload.role in ALLOWED_ROLES else "viewer"
    user = User(
        email=payload.email.lower(),
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role=role,
        age=payload.age,
        gender=payload.gender,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Ese correo ya está registrado") from exc
    await db.refresh(user)
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: DbDep) -> TokenOut:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Correo o clave incorrectos")
    token = create_access_token(user_id=user.id, role=user.role)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current: CurrentUser) -> UserOut:
    return UserOut.model_validate(current)


@router.patch("/me", response_model=UserOut)
async def update_me(payload: ProfileUpdateIn, db: DbDep, current: CurrentUser) -> UserOut:
    current.gender = payload.gender
    await db.commit()
    return UserOut.model_validate(current)
