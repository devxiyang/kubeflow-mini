"""FastAPI应用"""

from datetime import timedelta, datetime
from typing import List
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi_utils.tasks import repeat_every
import asyncio
import json

from .config import settings
from .models import init_database
from .schemas import (
    User, UserCreate, Project, ProjectCreate, MLJob, MLJobCreate, Token
)
from .crud import (
    create_user, get_user_by_username, get_users,
    create_project, get_project, get_projects, get_user_projects,
    create_mljob, get_mljob, get_mljobs, get_project_mljobs, get_user_mljobs,
    update_mljob_status, sync_mljob_status
)
from .security import (
    authenticate_user, create_access_token,
    get_current_active_user
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend service for managing ML jobs and metadata",
    version=settings.VERSION
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_database(
    provider=settings.DATABASE_PROVIDER,
    filename=settings.DATABASE_FILENAME
)

# 定时任务
@app.on_event("startup")
@repeat_every(seconds=settings.K8S_SYNC_INTERVAL)
async def sync_job_status():
    """定期从Kubernetes同步MLJob状态"""
    try:
        # 分批同步以避免超时
        with db_session:
            active_jobs = select(j for j in MLJob if j.status not in ["Succeeded", "Failed", "Deleted"])
            for i in range(0, len(active_jobs), settings.SYNC_BATCH_SIZE):
                batch = active_jobs[i:i + settings.SYNC_BATCH_SIZE]
                for job in batch:
                    try:
                        sync_mljob_status()
                    except Exception as e:
                        logger.error(f"Failed to sync job {job.job_id}: {str(e)}")
                        # 更新错误计数
                        job.sync_errors = (job.sync_errors or 0) + 1
                        # 如果错误次数超过阈值，标记为失败
                        if job.sync_errors >= settings.SYNC_ERROR_THRESHOLD:
                            job.status = "failed"
                            job.message = f"Failed to sync status after {job.sync_errors} attempts"
    except Exception as e:
        logger.error(f"Failed to sync job status: {str(e)}")

@app.on_event("startup")
@repeat_every(seconds=settings.RESOURCE.cleanup_interval)
async def cleanup_resources():
    """定期清理过期资源"""
    try:
        with db_session:
            # 1. 清理已完成的旧任务
            cutoff_date = datetime.utcnow() - timedelta(days=settings.RESOURCE.max_job_age)
            old_jobs = select(j for j in MLJob 
                            if j.status in ["Succeeded", "Failed", "Deleted"]
                            and j.updated_at < cutoff_date)
            
            for job in old_jobs:
                try:
                    # 删除k8s资源
                    delete_k8s_mljob(job.name, job.namespace)
                except Exception as e:
                    logger.error(f"Failed to delete k8s resource for job {job.job_id}: {str(e)}")
                # 删除数据库记录
                job.delete()
            
            # 2. 检查资源一致性
            active_jobs = select(j for j in MLJob 
                               if j.status not in ["Succeeded", "Failed", "Deleted"])
            
            for job in active_jobs:
                try:
                    # 检查k8s资源是否存在
                    k8s_jobs = k8s_api.list_namespaced_custom_object(
                        group=settings.K8S_GROUP,
                        version=settings.K8S_VERSION,
                        namespace=job.namespace,
                        plural=settings.K8S_PLURAL,
                        label_selector=f"job-id={job.job_id}"
                    )
                    
                    if not k8s_jobs.get("items"):
                        # k8s资源不存在，尝试重建
                        if job.sync_errors and job.sync_errors >= settings.SYNC_ERROR_THRESHOLD:
                            # 如果已经多次失败，标记为错误
                            job.status = "failed"
                            job.message = "Kubernetes resource lost and recreation failed"
                        else:
                            # 尝试重建资源
                            k8s_spec = json.loads(job.training)
                            create_k8s_mljob(
                                name=job.name,
                                namespace=job.namespace,
                                job_id=job.job_id,
                                spec=k8s_spec
                            )
                            job.sync_errors = (job.sync_errors or 0) + 1
                            
                except Exception as e:
                    logger.error(f"Failed to check resource consistency for job {job.job_id}: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Failed to cleanup resources: {str(e)}")

# 认证路由
@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """用户登录"""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# 用户路由
@app.post("/users/", response_model=User)
async def create_new_user(user: UserCreate):
    """创建用户"""
    db_user = get_user_by_username(user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return create_user(user)

@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    return current_user

@app.get("/users/", response_model=List[User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """获取用户列表"""
    users = get_users(skip=skip, limit=limit)
    return users

# 项目路由
@app.post("/projects/", response_model=Project)
async def create_new_project(
    project: ProjectCreate,
    current_user: User = Depends(get_current_active_user)
):
    """创建项目"""
    return create_project(project=project, owner_id=current_user.id)

@app.get("/projects/", response_model=List[Project])
async def read_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """获取项目列表"""
    projects = get_projects(skip=skip, limit=limit)
    return projects

@app.get("/projects/me/", response_model=List[Project])
async def read_user_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的项目列表"""
    projects = get_user_projects(user_id=current_user.id, skip=skip, limit=limit)
    return projects

@app.get("/projects/{project_id}", response_model=Project)
async def read_project(
    project_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取项目详情"""
    project = get_project(project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# ML任务路由
@app.post("/mljobs/", response_model=MLJob)
async def create_new_mljob(
    mljob: MLJobCreate,
    current_user: User = Depends(get_current_active_user)
):
    """创建ML任务"""
    # 检查项目是否存在
    project = get_project(project_id=mljob.project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # 检查用户是否有权限
    if project.owner.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    
    # 检查项目配额
    project_jobs = get_project_mljobs(project_id=mljob.project_id)
    if len(project_jobs) >= project.max_jobs:
        raise HTTPException(status_code=400, detail="Project job quota exceeded")
    
    return create_mljob(mljob=mljob, user_id=current_user.id)

@app.get("/mljobs/", response_model=List[MLJob])
async def read_mljobs(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """获取ML任务列表"""
    mljobs = get_mljobs(skip=skip, limit=limit)
    return mljobs

@app.get("/mljobs/me/", response_model=List[MLJob])
async def read_user_mljobs(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """获取当前用户的ML任务列表"""
    mljobs = get_user_mljobs(user_id=current_user.id, skip=skip, limit=limit)
    return mljobs

@app.get("/projects/{project_id}/mljobs/", response_model=List[MLJob])
async def read_project_mljobs(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user)
):
    """获取项目的ML任务列表"""
    project = get_project(project_id=project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    mljobs = get_project_mljobs(project_id=project_id, skip=skip, limit=limit)
    return mljobs

@app.get("/mljobs/{job_id}", response_model=MLJob)
async def read_mljob(
    job_id: int,
    current_user: User = Depends(get_current_active_user)
):
    """获取ML任务详情"""
    mljob = get_mljob(job_id=job_id)
    if mljob is None:
        raise HTTPException(status_code=404, detail="ML job not found")
    return mljob

@app.put("/mljobs/{job_id}/status")
async def update_job_status(
    job_id: int,
    status: str,
    current_user: User = Depends(get_current_active_user)
):
    """更新ML任务状态"""
    mljob = get_mljob(job_id=job_id)
    if mljob is None:
        raise HTTPException(status_code=404, detail="ML job not found")
    if mljob.user.id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_mljob_status(job_id=job_id, status=status)
    return {"ok": True} 