"""CRUD操作"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from pony.orm import db_session, select
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .models import User, Project, MLJob, Notebook
from .schemas import UserCreate, ProjectCreate, MLJobCreate, NotebookCreate, NotebookUpdate
from .security import get_password_hash
from .config import settings
from .k8s import (
    create_mljob_resource, update_mljob_resource,
    delete_mljob_resource, get_mljob_status,
    create_notebook_resources, update_notebook_resources,
    delete_notebook_resources, get_notebook_endpoint,
    create_namespace, update_namespace_quota, delete_namespace
)

# 配置日志
logger = logging.getLogger(__name__)

# 初始化k8s客户端
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

# Kubernetes API客户端
k8s_api = client.CustomObjectsApi()

# User operations
@db_session
def create_user(user: UserCreate) -> User:
    """创建用户
    
    同时在数据库和Kubernetes中创建Owner资源
    """
    try:
        # 1. 创建数据库记录
        db_user = User(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            hashed_password=get_password_hash(user.password)
        )
        
        # 2. 创建Kubernetes Owner资源
        k8s_spec = {
            "username": user.username,
            "email": user.email,
            "fullName": user.full_name,
            "role": "user",  # 默认角色
            "quotas": {
                "maxProjects": 5,  # 默认配额
                "maxJobsPerProject": 10
            }
        }
        
        create_k8s_owner(user.username, "default", k8s_spec)
        return db_user
        
    except Exception as e:
        # 如果出现错误,清理已创建的资源
        if "db_user" in locals():
            try:
                k8s_api.delete_namespaced_custom_object(
                    group=settings.K8S_GROUP,
                    version=settings.K8S_VERSION,
                    namespace="default",
                    plural="owners",
                    name=db_user.username
                )
            except:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

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
    """创建项目
    
    同时创建:
    1. 数据库记录
    2. Kubernetes Namespace
    3. ResourceQuota
    """
    try:
        # 1. 获取所有者信息
        owner = User.get(id=owner_id)
        if not owner:
            raise HTTPException(status_code=404, detail="Owner not found")
            
        # 2. 创建数据库记录
        db_project = Project(
            name=project.name,
            description=project.description,
            gpu_limit=project.gpu_limit,
            cpu_limit=project.cpu_limit,
            memory_limit=project.memory_limit,
            max_jobs=project.max_jobs,
            owner=owner_id
        )
        
        try:
            # 3. 创建Kubernetes Namespace和ResourceQuota
            create_namespace(
                name=project.name,
                labels={
                    "owner": owner.username,
                    "project": project.name
                }
            )
            
            # 4. 设置资源配额
            update_namespace_quota(
                name=project.name,
                cpu_limit=project.cpu_limit,
                memory_limit=project.memory_limit,
                gpu_limit=project.gpu_limit
            )
            
            return db_project
            
        except Exception as e:
            # 如果创建k8s资源失败,清理已创建的资源
            try:
                delete_namespace(project.name)
            except:
                pass
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create Kubernetes resources: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create project: {str(e)}"
        )

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

@db_session
def update_project(project_id: int, project: ProjectCreate) -> Project:
    """更新项目
    
    同时更新:
    1. 数据库记录
    2. Namespace ResourceQuota
    """
    try:
        # 1. 获取项目记录
        db_project = Project.get(id=project_id)
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # 2. 更新数据库记录
        db_project.description = project.description
        db_project.gpu_limit = project.gpu_limit
        db_project.cpu_limit = project.cpu_limit
        db_project.memory_limit = project.memory_limit
        db_project.max_jobs = project.max_jobs
        db_project.updated_at = datetime.utcnow()
        
        # 3. 更新资源配额
        update_namespace_quota(
            name=db_project.name,
            cpu_limit=project.cpu_limit,
            memory_limit=project.memory_limit,
            gpu_limit=project.gpu_limit
        )
        
        return db_project
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update project: {str(e)}"
        )

@db_session
def delete_project(project_id: int):
    """删除项目
    
    同时删除:
    1. 数据库记录
    2. Kubernetes Namespace(会自动删除所有关联资源)
    """
    try:
        # 1. 获取项目记录
        db_project = Project.get(id=project_id)
        if not db_project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # 2. 删除Kubernetes Namespace
        try:
            delete_namespace(db_project.name)
        except Exception as e:
            logger.error(f"Failed to delete namespace {db_project.name}: {str(e)}")
            
        # 3. 删除数据库记录
        db_project.delete()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete project: {str(e)}"
        )

# MLJob operations
@db_session
def create_mljob(mljob: MLJobCreate, user_id: int) -> MLJob:
    """创建ML任务
    
    先在数据库中创建记录,然后尝试创建Kubernetes资源
    如果Kubernetes资源创建失败,保留数据库记录,由状态同步任务处理
    """
    try:
        # 1. 创建数据库记录
        db_mljob = MLJob(
            job_id=mljob.job_id,
            name=f"mljob-{mljob.job_id}",
            namespace=mljob.namespace or "default",
            description=mljob.description,
            status="pending",
            project=mljob.project_id,
            user=user_id
        )
        
        # 提交数据库事务,确保记录创建成功
        db.commit()
        
        try:
            # 2. 尝试创建Kubernetes资源
            k8s_spec = {
                "project": db_mljob.project.name,
                "owner": db_mljob.user.username,
                "description": db_mljob.description,
                "training": mljob.training_spec  # 直接使用传入的training配置
            }
            
            create_mljob_resource(
                name=db_mljob.name,
                namespace=db_mljob.namespace,
                job_id=db_mljob.job_id,
                spec=k8s_spec
            )
        except Exception as e:
            # 如果创建k8s资源失败,记录错误状态
            logger.error(f"Failed to create Kubernetes resource for job {db_mljob.job_id}: {str(e)}")
            db_mljob.status = "error"
            db_mljob.message = f"Failed to create Kubernetes resource: {str(e)}"
            db_mljob.updated_at = datetime.utcnow()
            
        return db_mljob
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create MLJob: {str(e)}"
        )

@db_session
def update_mljob(job_id: str, mljob: MLJobCreate) -> MLJob:
    """更新ML任务
    
    同时更新数据库和Kubernetes中的MLJob资源
    """
    try:
        # 1. 更新数据库记录
        db_job = MLJob.get(job_id=job_id)  # 通过job_id查找
        if not db_job:
            raise HTTPException(status_code=404, detail="MLJob not found")
            
        # 更新字段
        db_job.description = mljob.description
        db_job.updated_at = datetime.utcnow()
        
        # 2. 更新Kubernetes资源
        k8s_spec = {
            "project": db_job.project.name,
            "owner": db_job.user.username,
            "description": db_job.description,
            "training": mljob.training_spec  # 直接使用传入的training配置
        }
        
        update_mljob_resource(db_job.name, db_job.namespace, k8s_spec)
        return db_job
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update MLJob: {str(e)}"
        )

@db_session
def delete_mljob(job_id: str):
    """删除ML任务
    
    同时删除数据库和Kubernetes中的MLJob资源
    """
    try:
        # 1. 获取数据库记录
        db_job = MLJob.get(job_id=job_id)  # 通过job_id查找
        if not db_job:
            raise HTTPException(status_code=404, detail="MLJob not found")
            
        # 2. 删除Kubernetes资源
        delete_mljob_resource(db_job.name, db_job.namespace)
        
        # 3. 删除数据库记录
        db_job.delete()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete MLJob: {str(e)}"
        )

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

# Notebook operations
@db_session
def create_notebook(notebook: NotebookCreate, user_id: int) -> Notebook:
    """创建Notebook
    
    同时在数据库和Kubernetes中创建Notebook资源
    """
    try:
        # 1. 检查项目是否存在
        project = Project.get(id=notebook.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        # 2. 创建数据库记录
        db_notebook = Notebook(
            name=notebook.name,
            description=notebook.description,
            image=notebook.image,
            gpu_limit=notebook.gpu_limit,
            cpu_limit=notebook.cpu_limit,
            memory_limit=notebook.memory_limit,
            project=notebook.project_id,
            user=user_id
        )
        
        # 提交数据库事务,确保记录创建成功
        db.commit()
        
        try:
            # 3. 创建Kubernetes资源
            service_name = f"notebook-{db_notebook.id}"
            k8s_spec = {
                "image": notebook.image,
                "resources": {
                    "limits": {
                        "nvidia.com/gpu": notebook.gpu_limit,
                        "cpu": str(notebook.cpu_limit),
                        "memory": notebook.memory_limit
                    },
                    "requests": {
                        "cpu": str(notebook.cpu_limit / 2),
                        "memory": _halve_memory(notebook.memory_limit)
                    }
                },
                "project": project.name,
                "owner": db_notebook.user.username
            }
            
            # 创建Deployment和Service
            create_notebook_resources(
                name=service_name,
                namespace=project.name,
                spec=k8s_spec
            )
            
            # 更新数据库记录
            db_notebook.service_name = service_name
            db_notebook.status = "running"
            db_notebook.started_at = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Failed to create Kubernetes resources for notebook {db_notebook.id}: {str(e)}")
            db_notebook.status = "error"
            db_notebook.message = f"Failed to create Kubernetes resources: {str(e)}"
            
        return db_notebook
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create notebook: {str(e)}"
        )

@db_session
def update_notebook(notebook_id: int, notebook: NotebookUpdate) -> Notebook:
    """更新Notebook
    
    同时更新数据库和Kubernetes中的资源
    """
    try:
        # 1. 获取数据库记录
        db_notebook = Notebook.get(id=notebook_id)
        if not db_notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
            
        # 2. 更新数据库记录
        if notebook.description is not None:
            db_notebook.description = notebook.description
        if notebook.gpu_limit is not None:
            db_notebook.gpu_limit = notebook.gpu_limit
        if notebook.cpu_limit is not None:
            db_notebook.cpu_limit = notebook.cpu_limit
        if notebook.memory_limit is not None:
            db_notebook.memory_limit = notebook.memory_limit
            
        db_notebook.updated_at = datetime.utcnow()
        
        # 3. 更新Kubernetes资源
        if db_notebook.status == "running":
            try:
                k8s_spec = {
                    "image": db_notebook.image,
                    "resources": {
                        "limits": {
                            "nvidia.com/gpu": db_notebook.gpu_limit,
                            "cpu": str(db_notebook.cpu_limit),
                            "memory": db_notebook.memory_limit
                        },
                        "requests": {
                            "cpu": str(db_notebook.cpu_limit / 2),
                            "memory": _halve_memory(db_notebook.memory_limit)
                        }
                    },
                    "project": db_notebook.project.name,
                    "owner": db_notebook.user.username
                }
                
                update_notebook_resources(
                    name=db_notebook.service_name,
                    namespace=db_notebook.project.name,
                    spec=k8s_spec
                )
                
            except Exception as e:
                logger.error(f"Failed to update Kubernetes resources for notebook {notebook_id}: {str(e)}")
                db_notebook.status = "error"
                db_notebook.message = f"Failed to update Kubernetes resources: {str(e)}"
                
        return db_notebook
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notebook: {str(e)}"
        )

@db_session
def delete_notebook(notebook_id: int):
    """删除Notebook
    
    同时删除数据库和Kubernetes中的资源
    """
    try:
        # 1. 获取数据库记录
        db_notebook = Notebook.get(id=notebook_id)
        if not db_notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
            
        # 2. 删除Kubernetes资源
        if db_notebook.service_name:
            try:
                delete_notebook_resources(
                    name=db_notebook.service_name,
                    namespace=db_notebook.project.name
                )
            except Exception as e:
                logger.error(f"Failed to delete Kubernetes resources for notebook {notebook_id}: {str(e)}")
                
        # 3. 删除数据库记录
        db_notebook.delete()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete notebook: {str(e)}"
        )

@db_session
def start_notebook(notebook_id: int) -> Notebook:
    """启动Notebook
    
    同时:
    1. 创建Kubernetes资源
    2. 启动租约计时
    """
    try:
        db_notebook = Notebook.get(id=notebook_id)
        if not db_notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
            
        # 检查租约状态
        if db_notebook.lease_status == "expired":
            raise HTTPException(status_code=400, detail="Notebook lease has expired")
            
        # 获取项目namespace
        namespace = f"project-{db_notebook.project.name}"
            
        # 创建Kubernetes资源
        create_notebook_resources(
            name=db_notebook.name,
            namespace=namespace,
            spec={
                "image": db_notebook.image,
                "resources": {
                    "limits": {
                        "nvidia.com/gpu": db_notebook.gpu_limit,
                        "cpu": str(db_notebook.cpu_limit),
                        "memory": db_notebook.memory_limit
                    },
                    "requests": {
                        "nvidia.com/gpu": db_notebook.gpu_limit,
                        "cpu": str(db_notebook.cpu_limit/2),
                        "memory": _halve_memory(db_notebook.memory_limit)
                    }
                }
            }
        )
        
        # 获取访问地址
        endpoint = get_notebook_endpoint(db_notebook.name, namespace)
        
        # 更新状态
        db_notebook.status = "running"
        db_notebook.message = "Notebook is running"
        db_notebook.service_name = db_notebook.name
        db_notebook.endpoint = endpoint
        db_notebook.started_at = datetime.utcnow()
        db_notebook.updated_at = datetime.utcnow()
        
        # 启动租约
        db_notebook.lease_start = datetime.utcnow()
        db_notebook.lease_status = "active"
        
        return db_notebook
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start notebook: {str(e)}"
        )

@db_session
def stop_notebook(notebook_id: int) -> Notebook:
    """停止Notebook
    
    同时:
    1. 删除Kubernetes资源
    2. 暂停租约计时
    """
    try:
        db_notebook = Notebook.get(id=notebook_id)
        if not db_notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
            
        # 获取项目namespace
        namespace = f"project-{db_notebook.project.name}"
            
        # 删除Kubernetes资源
        delete_notebook_resources(db_notebook.name, namespace)
        
        # 更新状态
        db_notebook.status = "stopped"
        db_notebook.message = "Notebook is stopped"
        db_notebook.service_name = None
        db_notebook.endpoint = None
        db_notebook.stopped_at = datetime.utcnow()
        db_notebook.updated_at = datetime.utcnow()
        
        # 暂停租约
        db_notebook.lease_status = "inactive"
        
        return db_notebook
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop notebook: {str(e)}"
        )

@db_session
def renew_notebook_lease(notebook_id: int) -> Notebook:
    """续租Notebook"""
    try:
        db_notebook = Notebook.get(id=notebook_id)
        if not db_notebook:
            raise HTTPException(status_code=404, detail="Notebook not found")
            
        # 检查是否可以续租
        if db_notebook.lease_renewal_count >= db_notebook.max_lease_renewals:
            raise HTTPException(status_code=400, detail="Maximum lease renewals reached")
            
        # 检查当前租约状态
        if db_notebook.lease_status != "active":
            raise HTTPException(status_code=400, detail="Notebook lease is not active")
            
        # 续租
        db_notebook.lease_start = datetime.utcnow()
        db_notebook.lease_renewal_count += 1
        db_notebook.updated_at = datetime.utcnow()
        
        return db_notebook
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to renew notebook lease: {str(e)}"
        )

@db_session
def check_notebook_leases():
    """检查所有Notebook租约状态"""
    try:
        # 获取所有运行中的notebook
        active_notebooks = select(n for n in Notebook if n.status == "running" and n.lease_status == "active")[:]
        
        now = datetime.utcnow()
        for notebook in active_notebooks:
            if notebook.lease_start:
                # 计算租约是否过期
                lease_end = notebook.lease_start + timedelta(hours=notebook.lease_duration)
                if now > lease_end:
                    # 租约过期,停止notebook
                    notebook.lease_status = "expired"
                    notebook.message = "Lease expired"
                    notebook.updated_at = now
                    
                    try:
                        stop_notebook(notebook.id)
                    except:
                        logger.error(f"Failed to stop expired notebook {notebook.id}")
                        
    except Exception as e:
        logger.error(f"Failed to check notebook leases: {str(e)}")

@db_session
def get_notebook(notebook_id: int) -> Optional[Notebook]:
    """获取Notebook"""
    return Notebook.get(id=notebook_id)

@db_session
def get_notebooks(skip: int = 0, limit: int = 100) -> List[Notebook]:
    """获取Notebook列表"""
    return select(n for n in Notebook).offset(skip).limit(limit)[:]

@db_session
def get_project_notebooks(project_id: int, skip: int = 0, limit: int = 100) -> List[Notebook]:
    """获取项目的Notebook列表"""
    return select(n for n in Notebook if n.project.id == project_id).offset(skip).limit(limit)[:]

@db_session
def get_user_notebooks(user_id: int, skip: int = 0, limit: int = 100) -> List[Notebook]:
    """获取用户的Notebook列表"""
    return select(n for n in Notebook if n.user.id == user_id).offset(skip).limit(limit)[:]

def _halve_memory(memory: str) -> str:
    """将内存限制减半"""
    try:
        bytes = _convert_memory_to_bytes(memory)
        return _convert_bytes_to_memory(bytes // 2)
    except:
        return memory 