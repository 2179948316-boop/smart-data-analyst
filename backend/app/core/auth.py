"""Authentication utilities — JWT tokens, password hashing, FastAPI dependencies."""

import os
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from app.core.database import AppSessionLocal
from app.models import User, Workspace, WorkspaceMember

# ── Config ──
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "smart-analyst-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7  # 7 days


# ── Password Hashing (direct bcrypt) ──
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ──
def create_access_token(user_id: int, workspace_id: int | None = None) -> str:
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "exp": expire,
    }
    if workspace_id:
        payload["ws"] = workspace_id
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效或过期的令牌",
        )


# ── FastAPI Dependencies ──
security = HTTPBearer(auto_error=False)


def get_db():
    """Yield a database session."""
    db = AppSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
        )
    payload = decode_token(credentials.credentials)
    user_id = int(payload.get("sub", 0))
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在或已被禁用",
        )
    return user


def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of raising if no token."""
    if not credentials:
        return None
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub", 0))
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except HTTPException:
        return None


def get_current_workspace(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> Workspace | None:
    """Get the workspace from the JWT token's ws claim."""
    if not credentials:
        return None
    payload = decode_token(credentials.credentials)
    ws_id = payload.get("ws")
    if not ws_id:
        return None
    return db.query(Workspace).filter(Workspace.id == int(ws_id)).first()


def require_workspace_role(*roles: str):
    """Dependency factory: require the user to have one of the given roles in the current workspace."""
    def checker(
        user: User = Depends(get_current_user),
        workspace: Workspace | None = Depends(get_current_workspace),
        db: Session = Depends(get_db),
    ):
        if not workspace:
            raise HTTPException(status_code=400, detail="未选择工作空间")
        member = (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.workspace_id == workspace.id, WorkspaceMember.user_id == user.id)
            .first()
        )
        if not member or member.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要角色: {', '.join(roles)}",
            )
        return member
    return checker
