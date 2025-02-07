"""CRUD操作"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from pony.orm import db_session, select
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .models import User, Project, MLJob
from .schemas import UserCreate, ProjectCreate, MLJobCreate
from .security import get_password_hash
from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

# 初始化k8s客户端
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

# Kubernetes API客户端
k8s_api = client.CustomObjectsApi()

def create_k8s_mljob(name: str, namespace: str, spec: dict) -> dict:
    """在Kubernetes中创建MLJob资源
    
    Args:
        name: 资源名称
        namespace: 命名空间
        spec: MLJob规格
        
    Returns:
        dict: 创建的资源对象
    """
    try:
        body = {
            "apiVersion": f"{settings.K8S_GROUP}/{settings.K8S_VERSION}",
            "kind": "MLJob",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": spec
        }
        
        return k8s_api.create_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural=settings.K8S_PLURAL,
            body=body
        )
    except ApiException as e:
        logger.error(f"Failed to create MLJob in Kubernetes: {str(e)}")
        raise

def update_k8s_mljob(name: str, namespace: str, spec: dict) -> dict:
    """在Kubernetes中更新MLJob资源
    
    Args:
        name: 资源名称
        namespace: 命名空间
        spec: 新的MLJob规格
        
    Returns:
        dict: 更新后的资源对象
    """
    try:
        body = {
            "apiVersion": f"{settings.K8S_GROUP}/{settings.K8S_VERSION}",
            "kind": "MLJob",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": spec
        }
        
        return k8s_api.patch_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural=settings.K8S_PLURAL,
            name=name,
            body=body
        )
    except ApiException as e:
        logger.error(f"Failed to update MLJob in Kubernetes: {str(e)}")
        raise

def delete_k8s_mljob(name: str, namespace: str):
    """在Kubernetes中删除MLJob资源
    
    Args:
        name: 资源名称
        namespace: 命名空间
    """
    try:
        k8s_api.delete_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural=settings.K8S_PLURAL,
            name=name
        )
    except ApiException as e:
        if e.status != 404:  # 忽略已删除的资源
            logger.error(f"Failed to delete MLJob in Kubernetes: {str(e)}")
            raise

def create_k8s_project(name: str, namespace: str, spec: dict) -> dict:
    """在Kubernetes中创建Project资源"""
    try:
        body = {
            "apiVersion": f"{settings.K8S_GROUP}/{settings.K8S_VERSION}",
            "kind": "Project",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": spec
        }
        
        return k8s_api.create_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural="projects",
            body=body
        )
    except ApiException as e:
        logger.error(f"Failed to create Project in Kubernetes: {str(e)}")
        raise

def create_k8s_owner(name: str, namespace: str, spec: dict) -> dict:
    """在Kubernetes中创建Owner资源"""
    try:
        body = {
            "apiVersion": f"{settings.K8S_GROUP}/{settings.K8S_VERSION}",
            "kind": "Owner",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": spec
        }
        
        return k8s_api.create_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural="owners",
            body=body
        )
    except ApiException as e:
        logger.error(f"Failed to create Owner in Kubernetes: {str(e)}")
        raise

def sync_mljob_status():
    """从Kubernetes同步MLJob状态
    
    只同步需要更新状态的任务,通过任务ID精确获取
    """
    try:
        with db_session:
            # 1. 获取需要同步状态的任务
            # 选择状态不是终态的任务
            active_jobs = select(j for j in MLJob if j.status not in ["Succeeded", "Failed", "Deleted"])[:]
            
            # 2. 批量获取这些任务的状态
            for job in active_jobs:
                try:
                    # 通过任务ID精确获取状态
                    k8s_job = k8s_api.get_namespaced_custom_object(
                        group=settings.K8S_GROUP,
                        version=settings.K8S_VERSION,
                        namespace=job.namespace,
                        plural=settings.K8S_PLURAL,
                        name=job.name
                    )
                    
                    status = k8s_job.get("status", {})
                    
                    # 更新状态
                    job.status = status.get("phase", "Unknown")
                    job.message = status.get("message")
                    job.updated_at = datetime.utcnow()
                    
                    # 更新时间戳
                    if status.get("start_time") and not job.started_at:
                        job.started_at = datetime.fromisoformat(status["start_time"].rstrip("Z"))
                    if status.get("completion_time"):
                        job.completed_at = datetime.fromisoformat(status["completion_time"].rstrip("Z"))
                        
                    # 更新训练状态
                    if "training_status" in status:
                        job.training_status = json.dumps(status["training_status"])
                        
                except ApiException as e:
                    if e.status == 404:
                        # 资源已被删除
                        job.status = "Deleted"
                        job.message = "Resource not found in Kubernetes"
                        job.updated_at = datetime.utcnow()
                    else:
                        logger.error(f"Failed to get MLJob status for {job.namespace}/{job.name}: {str(e)}")
                except Exception as e:
                    logger.error(f"Error syncing MLJob {job.namespace}/{job.name}: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Failed to sync MLJob status: {str(e)}")

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
    
    同时在数据库和Kubernetes中创建Project资源
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
        
        # 3. 创建Kubernetes Project资源
        k8s_spec = {
            "owner": owner.username,
            "description": project.description,
            "quotas": {
                "gpu": project.gpu_limit,
                "cpu": project.cpu_limit,
                "memory": project.memory_limit,
                "maxJobs": project.max_jobs
            }
        }
        
        create_k8s_project(project.name, "default", k8s_spec)
        return db_project
        
    except HTTPException:
        raise
    except Exception as e:
        # 如果出现错误,清理已创建的资源
        if "db_project" in locals():
            try:
                k8s_api.delete_namespaced_custom_object(
                    group=settings.K8S_GROUP,
                    version=settings.K8S_VERSION,
                    namespace="default",
                    plural="projects",
                    name=db_project.name
                )
            except:
                pass
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

# MLJob operations
@db_session
def create_mljob(mljob: MLJobCreate, user_id: int) -> MLJob:
    """创建ML任务
    
    同时在数据库和Kubernetes中创建MLJob资源
    """
    try:
        # 1. 创建数据库记录
        db_mljob = MLJob(
            name=mljob.name,
            namespace=mljob.namespace or "default",
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
        
        # 2. 创建Kubernetes资源
        k8s_spec = {
            "job_id": str(db_mljob.id),
            "project": db_mljob.project.name,
            "owner": db_mljob.user.username,
            "description": db_mljob.description,
            "training": {
                "api_version": f"kubeflow.org/v1",
                "kind": f"{db_mljob.framework}Job",
                "spec": {
                    # 根据framework构造对应的training operator配置
                    f"{db_mljob.framework.lower()}ReplicaSpecs": {
                        "Worker": {
                            "replicas": 1,
                            "template": {
                                "spec": {
                                    "containers": [{
                                        "name": "training",
                                        "image": mljob.image,
                                        "command": [db_mljob.command],
                                        "args": json.loads(db_mljob.args),
                                        "env": json.loads(db_mljob.environment),
                                        "resources": {
                                            "limits": {
                                                "nvidia.com/gpu": db_mljob.gpu_request,
                                                "cpu": db_mljob.cpu_request,
                                                "memory": db_mljob.memory_request
                                            },
                                            "requests": {
                                                "nvidia.com/gpu": db_mljob.gpu_request,
                                                "cpu": db_mljob.cpu_request,
                                                "memory": db_mljob.memory_request
                                            }
                                        }
                                    }]
                                }
                            }
                        }
                    }
                }
            }
        }
        
        create_k8s_mljob(db_mljob.name, db_mljob.namespace, k8s_spec)
        return db_mljob
        
    except Exception as e:
        # 如果出现错误,清理已创建的资源
        if "db_mljob" in locals():
            try:
                delete_k8s_mljob(db_mljob.name, db_mljob.namespace)
            except:
                pass
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create MLJob: {str(e)}"
        )

@db_session
def update_mljob(job_id: int, mljob: MLJobCreate) -> MLJob:
    """更新ML任务
    
    同时更新数据库和Kubernetes中的MLJob资源
    """
    try:
        # 1. 更新数据库记录
        db_job = MLJob.get(id=job_id)
        if not db_job:
            raise HTTPException(status_code=404, detail="MLJob not found")
            
        # 更新字段
        db_job.description = mljob.description
        db_job.gpu_request = mljob.gpu_request
        db_job.cpu_request = mljob.cpu_request
        db_job.memory_request = mljob.memory_request
        db_job.command = mljob.command
        db_job.args = json.dumps(mljob.args)
        db_job.environment = json.dumps(mljob.environment)
        db_job.updated_at = datetime.utcnow()
        
        # 2. 更新Kubernetes资源
        k8s_spec = {
            "job_id": str(db_job.id),
            "project": db_job.project.name,
            "owner": db_job.user.username,
            "description": db_job.description,
            "training": {
                "api_version": f"kubeflow.org/v1",
                "kind": f"{db_job.framework}Job",
                "spec": {
                    f"{db_job.framework.lower()}ReplicaSpecs": {
                        "Worker": {
                            "replicas": 1,
                            "template": {
                                "spec": {
                                    "containers": [{
                                        "name": "training",
                                        "image": mljob.image,
                                        "command": [db_job.command],
                                        "args": json.loads(db_job.args),
                                        "env": json.loads(db_job.environment),
                                        "resources": {
                                            "limits": {
                                                "nvidia.com/gpu": db_job.gpu_request,
                                                "cpu": db_job.cpu_request,
                                                "memory": db_job.memory_request
                                            },
                                            "requests": {
                                                "nvidia.com/gpu": db_job.gpu_request,
                                                "cpu": db_job.cpu_request,
                                                "memory": db_job.memory_request
                                            }
                                        }
                                    }]
                                }
                            }
                        }
                    }
                }
            }
        }
        
        update_k8s_mljob(db_job.name, db_job.namespace, k8s_spec)
        return db_job
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update MLJob: {str(e)}"
        )

@db_session
def delete_mljob(job_id: int):
    """删除ML任务
    
    同时删除数据库和Kubernetes中的MLJob资源
    """
    try:
        # 1. 获取数据库记录
        db_job = MLJob.get(id=job_id)
        if not db_job:
            raise HTTPException(status_code=404, detail="MLJob not found")
            
        # 2. 删除Kubernetes资源
        delete_k8s_mljob(db_job.name, db_job.namespace)
        
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