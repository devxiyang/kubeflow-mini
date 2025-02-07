"""CRUD操作"""

import json
from datetime import datetime
from typing import List, Optional
from pony.orm import db_session, select

from .models import User, Project, MLJob
from .schemas import UserCreate, ProjectCreate, MLJobCreate
from .security import get_password_hash

# User operations
@db_session
def create_user(user: UserCreate) -> User:
    """创建用户"""
    db_user = User(
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        hashed_password=get_password_hash(user.password)
    )
    return db_user

@db_session
def get_user(user_id: int) -> Optional[User]:
    """获取用户"""
    return User.get(id=user_id)

@db_session
def get_user_by_username(username: str) -> Optional[User]:
    """通过用户名获取用户"""
    return User.get(username=username)

@db_session
def get_users(skip: int = 0, limit: int = 100) -> List[User]:
    """获取用户列表"""
    return select(u for u in User).offset(skip).limit(limit)[:]

# Project operations
@db_session
def create_project(project: ProjectCreate, owner_id: int) -> Project:
    """创建项目"""
    db_project = Project(
        name=project.name,
        description=project.description,
        gpu_limit=project.gpu_limit,
        cpu_limit=project.cpu_limit,
        memory_limit=project.memory_limit,
        max_jobs=project.max_jobs,
        owner=owner_id
    )
    return db_project

@db_session
def get_project(project_id: int) -> Optional[Project]:
    """获取项目"""
    return Project.get(id=project_id)

@db_session
def get_projects(skip: int = 0, limit: int = 100) -> List[Project]:
    """获取项目列表"""
    return select(p for p in Project).offset(skip).limit(limit)[:]

@db_session
def get_user_projects(user_id: int, skip: int = 0, limit: int = 100) -> List[Project]:
    """获取用户的项目列表"""
    return select(p for p in Project if p.owner.id == user_id).offset(skip).limit(limit)[:]

# MLJob operations
@db_session
def create_mljob(mljob: MLJobCreate, user_id: int) -> MLJob:
    """创建ML任务"""
    db_mljob = MLJob(
        name=mljob.name,
        description=mljob.description,
        framework=mljob.framework,
        gpu_request=mljob.gpu_request,
        cpu_request=mljob.cpu_request,
        memory_request=mljob.memory_request,
        command=mljob.command,
        args=json.dumps(mljob.args),
        environment=json.dumps(mljob.environment),
        status="pending",
        project=mljob.project_id,
        user=user_id
    )
    return db_mljob

@db_session
def get_mljob(job_id: int) -> Optional[MLJob]:
    """获取ML任务"""
    return MLJob.get(id=job_id)

@db_session
def get_mljobs(skip: int = 0, limit: int = 100) -> List[MLJob]:
    """获取ML任务列表"""
    return select(j for j in MLJob).offset(skip).limit(limit)[:]

@db_session
def get_project_mljobs(project_id: int, skip: int = 0, limit: int = 100) -> List[MLJob]:
    """获取项目的ML任务列表"""
    return select(j for j in MLJob if j.project.id == project_id).offset(skip).limit(limit)[:]

@db_session
def get_user_mljobs(user_id: int, skip: int = 0, limit: int = 100) -> List[MLJob]:
    """获取用户的ML任务列表"""
    return select(j for j in MLJob if j.user.id == user_id).offset(skip).limit(limit)[:]

@db_session
def update_mljob_status(job_id: int, status: str) -> Optional[MLJob]:
    """更新ML任务状态"""
    db_job = MLJob.get(id=job_id)
    if db_job:
        db_job.status = status
        db_job.updated_at = datetime.utcnow()
        if status == "running" and not db_job.started_at:
            db_job.started_at = datetime.utcnow()
        elif status in ["completed", "failed"]:
            db_job.completed_at = datetime.utcnow()
    return db_job 