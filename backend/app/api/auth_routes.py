"""Authentication & workspace team management routes."""

import re
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.auth import (
    hash_password, verify_password, create_access_token,
    get_current_user, get_current_workspace, get_db, require_workspace_role,
)
from app.core.database import AppSessionLocal, biz_engine
from app.models import User, Workspace, WorkspaceMember

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Request Models ──

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    workspace: dict | None = None


class CreateWorkspaceRequest(BaseModel):
    name: str
    description: str | None = None


class InviteMemberRequest(BaseModel):
    username: str
    role: str = "member"  # admin / member


class SelectWorkspaceRequest(BaseModel):
    workspace_id: int


# ── Helpers ──

def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name or user.username,
    }


def _workspace_to_dict(ws: Workspace, role: str | None = None) -> dict:
    return {
        "id": ws.id,
        "name": ws.name,
        "db_name": ws.db_name,
        "description": ws.description,
        "role": role,
    }


def _create_workspace_database(db_name: str):
    """Create a new MySQL database for a workspace."""
    # Sanitize db_name to prevent SQL injection
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]{0,63}$", db_name):
        raise ValueError(f"Invalid database name: {db_name}")

    with biz_engine.connect() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                         f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.commit()
    logger.info(f"Created workspace database: {db_name}")


# ── Auth Endpoints ──

@router.post("/api/auth/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    # Validate
    if len(req.username) < 2 or len(req.username) > 50:
        raise HTTPException(status_code=400, detail="用户名长度应在 2-50 之间")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    # Check uniqueness
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    # Create user
    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name or req.username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Auto-create a personal workspace
    db_name = f"ws_{user.id}_{re.sub(r'[^a-zA-Z0-9]', '_', user.username)[:30]}"
    try:
        _create_workspace_database(db_name)
    except Exception as e:
        logger.error(f"Failed to create workspace DB: {e}")
        db_name = f"ws_{user.id}"
        _create_workspace_database(db_name)

    workspace = Workspace(
        name=f"{user.display_name or user.username}的团队",
        db_name=db_name,
        owner_id=user.id,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    # Add owner as admin member
    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
    )
    db.add(member)
    db.commit()

    # Generate token
    token = create_access_token(user.id, workspace.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_to_dict(user),
        "workspace": _workspace_to_dict(workspace, "admin"),
    }


@router.post("/api/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login with username and password."""
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    # Get user's first workspace
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user.id)
        .first()
    )
    workspace = None
    role = None
    if membership:
        workspace = db.query(Workspace).filter(Workspace.id == membership.workspace_id).first()
        role = membership.role

    token = create_access_token(user.id, workspace.id if workspace else None)

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_to_dict(user),
        "workspace": _workspace_to_dict(workspace, role) if workspace else None,
    }


@router.get("/api/auth/me")
def get_me(user: User = Depends(get_current_user)):
    """Get current user info."""
    return {"user": _user_to_dict(user)}


@router.post("/api/auth/select-workspace")
def select_workspace(
    req: SelectWorkspaceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Switch to a different workspace (must be a member)."""
    membership = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == req.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="你不是该工作空间的成员")

    workspace = db.query(Workspace).filter(Workspace.id == req.workspace_id).first()
    token = create_access_token(user.id, workspace.id)

    return {
        "access_token": token,
        "token_type": "bearer",
        "workspace": _workspace_to_dict(workspace, membership.role),
    }


# ── Workspace Endpoints ──

@router.get("/api/workspaces")
def list_workspaces(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all workspaces the user belongs to."""
    memberships = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.user_id == user.id)
        .all()
    )
    result = []
    for m in memberships:
        ws = db.query(Workspace).filter(Workspace.id == m.workspace_id).first()
        if ws:
            result.append(_workspace_to_dict(ws, m.role))
    return {"workspaces": result}


@router.post("/api/workspaces")
def create_workspace(
    req: CreateWorkspaceRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new workspace (team)."""
    db_name = f"ws_{re.sub(r'[^a-zA-Z0-9]', '_', req.name)[:30]}_{int(datetime.now().timestamp())}"

    try:
        _create_workspace_database(db_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建数据库失败: {e}")

    workspace = Workspace(
        name=req.name,
        db_name=db_name,
        owner_id=user.id,
        description=req.description,
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)

    member = WorkspaceMember(
        workspace_id=workspace.id,
        user_id=user.id,
        role="admin",
    )
    db.add(member)
    db.commit()

    return {"workspace": _workspace_to_dict(workspace, "admin")}


@router.get("/api/workspaces/{workspace_id}/members")
def list_members(
    workspace_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List members of a workspace."""
    # Verify user is a member
    membership = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="你不是该工作空间的成员")

    members = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id)
        .all()
    )
    result = []
    for m in members:
        u = db.query(User).filter(User.id == m.user_id).first()
        result.append({
            "user_id": u.id,
            "username": u.username,
            "display_name": u.display_name or u.username,
            "role": m.role,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
        })
    return {"members": result}


@router.post("/api/workspaces/{workspace_id}/invite")
def invite_member(
    workspace_id: int,
    req: InviteMemberRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Invite a user to the workspace (admin only)."""
    # Verify admin
    admin_membership = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
            WorkspaceMember.role == "admin",
        )
        .first()
    )
    if not admin_membership:
        raise HTTPException(status_code=403, detail="只有管理员可以邀请成员")

    # Find target user
    target = db.query(User).filter(User.username == req.username).first()
    if not target:
        raise HTTPException(status_code=404, detail=f"用户 '{req.username}' 不存在")

    # Check if already a member
    existing = (
        db.query(WorkspaceMember)
        .filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == target.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"用户 '{req.username}' 已经是成员")

    if req.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="角色必须是 admin 或 member")

    member = WorkspaceMember(
        workspace_id=workspace_id,
        user_id=target.id,
        role=req.role,
    )
    db.add(member)
    db.commit()

    return {"message": f"已邀请 {req.username} 加入团队（角色: {req.role}）"}


from datetime import datetime
