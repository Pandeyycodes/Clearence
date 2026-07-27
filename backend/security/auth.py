"""Authentication: password hashing + JWT issue/verify.

Recruiters (the tool's *users*, distinct from the candidates whose resumes are
screened) log in and receive a signed JWT. Later requests carry that token in
an `Authorization: Bearer <token>` header; the server verifies the signature
statelessly instead of hitting the database on every call.

Passwords are stored only as bcrypt hashes — never in plaintext. The signing
secret comes from CLEARANCE_SECRET_KEY; the baked-in default is for local dev
only and MUST be overridden in any real deployment.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt  # PyJWT
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.environ.get("CLEARANCE_SECRET_KEY",
                            "dev-only-insecure-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60  # 12 hours

# tokenUrl points clients (and the Swagger "Authorize" button) at the login route.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ----------------------------------------------------------- passwords
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


# ----------------------------------------------------------- tokens
def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": subject, "exp": expire}, SECRET_KEY,
                      algorithm=ALGORITHM)


_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials.",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency: return the authenticated recruiter's email, or 401.

    Attach with `user: str = Depends(get_current_user)` to protect a route.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise _credentials_error
    subject = payload.get("sub")
    if not subject:
        raise _credentials_error
    return subject
