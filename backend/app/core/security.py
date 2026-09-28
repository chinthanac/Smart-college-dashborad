import collections.abc
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

if not hasattr(collections, 'Mapping'):
    collections.Mapping = collections.abc.Mapping
if not hasattr(collections, 'Iterable'):
    collections.Iterable = collections.abc.Iterable
if not hasattr(collections, 'MutableMapping'):
    collections.MutableMapping = collections.abc.MutableMapping
if not hasattr(collections, 'Sequence'):
    collections.Sequence = collections.abc.Sequence

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {"sub": str(subject), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[settings.algorithm])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        user = db.query(User).filter(User.email == email).first()
    except (IndexError, SQLAlchemyError):
        raise credentials_exception

    if user is None:
        raise credentials_exception
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def get_current_faculty_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "FACULTY":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Faculty access required")
    return current_user


def get_current_student_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "STUDENT":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student access required")
    return current_user


def get_current_staff_user(current_user: User = Depends(get_current_user)) -> User:
    """Admin or Faculty. Read-only student views are shared by both, with
    Faculty scoped to their own department by the caller."""
    if current_user.role not in ("ADMIN", "FACULTY"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required")
    return current_user
