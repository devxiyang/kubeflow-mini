"""Operator工具函数"""

import logging
from typing import Optional, Dict, Any
from kubernetes import client
from kubernetes.client.rest import ApiException

from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

# ===================== Training Job 操作 =====================

def create_training_job(name: str, namespace: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """创建Training Job
    
    直接使用training-operator的CRD创建对应的Job
    """
    try:
        training = spec.get("training", {})
        if not training:
            raise ValueError("Training spec is required")
            
        api = client.CustomObjectsApi()
        
        # 准备Job配置
        job = {
            "apiVersion": training.get("api_version"),
            "kind": training.get("kind"),
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": training.get("spec", {})
        }
        
        # 从api_version解析group和version
        api_version = training.get("api_version", "").split("/")
        if len(api_version) != 2:
            raise ValueError("Invalid api_version format")
            
        return api.create_namespaced_custom_object(
            group=api_version[0],
            version=api_version[1],
            namespace=namespace,
            plural=training.get("kind", "").lower() + "s",
            body=job
        )
    except Exception as e:
        logger.error(f"Failed to create training job: {str(e)}")
        raise

def delete_training_job(name: str, namespace: str, spec: Dict[str, Any]) -> None:
    """删除Training Job
    
    直接删除training-operator的CRD资源
    """
    try:
        training = spec.get("training", {})
        if not training:
            return
            
        api = client.CustomObjectsApi()
        
        api_version = training.get("api_version", "").split("/")
        if len(api_version) != 2:
            return
            
        api.delete_namespaced_custom_object(
            group=api_version[0],
            version=api_version[1],
            namespace=namespace,
            plural=training.get("kind", "").lower() + "s",
            name=name
        )
    except Exception as e:
        logger.error(f"Failed to delete training job: {str(e)}")
        raise

def get_training_job_status(name: str, namespace: str, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """获取Training Job状态
    
    获取training-operator CRD资源的状态
    """
    try:
        training = spec.get("training", {})
        if not training:
            return None
            
        api = client.CustomObjectsApi()
        
        api_version = training.get("api_version", "").split("/")
        if len(api_version) != 2:
            return None
            
        job = api.get_namespaced_custom_object(
            group=api_version[0],
            version=api_version[1],
            namespace=namespace,
            plural=training.get("kind", "").lower() + "s",
            name=name
        )
        return job.get("status", {})
    except Exception as e:
        logger.error(f"Failed to get training job status: {str(e)}")
        return None

# ===================== Project 操作 =====================

def validate_project_quotas(spec: Dict[str, Any]) -> bool:
    """验证项目配额设置"""
    try:
        quotas = spec.get("quotas", {})
        return (
            isinstance(quotas.get("gpu_limit"), int) and
            isinstance(quotas.get("cpu_limit"), (int, float)) and
            isinstance(quotas.get("memory_limit"), str) and
            isinstance(quotas.get("max_jobs"), int)
        )
    except Exception:
        return False

def should_update_jobs(old_spec: Dict[str, Any], new_spec: Dict[str, Any]) -> bool:
    """检查是否需要更新MLJobs"""
    old_quotas = old_spec.get("quotas", {})
    new_quotas = new_spec.get("quotas", {})
    return old_quotas != new_quotas

def update_project_jobs(project_name: str, namespace: str, spec: Dict[str, Any]) -> None:
    """更新项目关联的MLJobs"""
    try:
        api = client.CustomObjectsApi()
        jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"project={project_name}"
        )
        
        for job in jobs.get("items", []):
            # 根据新的项目配额更新Job
            update_job_resources(job, spec.get("quotas", {}))
    except Exception as e:
        logger.error(f"Failed to update project jobs: {str(e)}")
        raise

def delete_project_jobs(project_name: str, namespace: str) -> None:
    """删除项目关联的MLJobs"""
    try:
        api = client.CustomObjectsApi()
        jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"project={project_name}"
        )
        
        for job in jobs.get("items", []):
            name = job["metadata"]["name"]
            api.delete_namespaced_custom_object(
                group=settings.GROUP,
                version=settings.VERSION,
                namespace=namespace,
                plural=settings.PLURAL,
                name=name
            )
    except Exception as e:
        logger.error(f"Failed to delete project jobs: {str(e)}")
        raise

# ===================== Owner 操作 =====================

def validate_owner_config(spec: Dict[str, Any]) -> bool:
    """验证Owner配置"""
    try:
        return (
            isinstance(spec.get("name"), str) and
            isinstance(spec.get("email"), str) and
            isinstance(spec.get("role"), str)
        )
    except Exception:
        return False

def should_update_owner_resources(old_spec: Dict[str, Any], new_spec: Dict[str, Any]) -> bool:
    """检查是否需要更新Owner关联资源"""
    return (
        old_spec.get("role") != new_spec.get("role") or
        old_spec.get("permissions") != new_spec.get("permissions")
    )

def update_owner_resources(owner_name: str, namespace: str, spec: Dict[str, Any]) -> None:
    """更新Owner关联的资源"""
    try:
        api = client.CustomObjectsApi()
        
        # 更新Projects
        projects = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural="projects",
            label_selector=f"owner={owner_name}"
        )
        
        for project in projects.get("items", []):
            # 根据新的Owner配置更新Project
            update_project_permissions(project, spec)
            
        # 更新MLJobs
        jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"owner={owner_name}"
        )
        
        for job in jobs.get("items", []):
            # 根据新的Owner配置更新Job
            update_job_permissions(job, spec)
    except Exception as e:
        logger.error(f"Failed to update owner resources: {str(e)}")
        raise

def delete_owner_resources(owner_name: str, namespace: str) -> None:
    """删除Owner关联的资源"""
    try:
        api = client.CustomObjectsApi()
        
        # 删除Projects
        projects = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural="projects",
            label_selector=f"owner={owner_name}"
        )
        
        for project in projects.get("items", []):
            name = project["metadata"]["name"]
            api.delete_namespaced_custom_object(
                group=settings.GROUP,
                version=settings.VERSION,
                namespace=namespace,
                plural="projects",
                name=name
            )
            
        # MLJobs会通过级联删除自动删除
    except Exception as e:
        logger.error(f"Failed to delete owner resources: {str(e)}")
        raise

# ===================== 资源验证 =====================

def validate_resource_requests(spec: Dict[str, Any]) -> bool:
    """验证资源请求"""
    try:
        for replica_spec in spec.values():
            if isinstance(replica_spec, dict):
                template = replica_spec.get("template", {})
                containers = template.get("spec", {}).get("containers", [])
                for container in containers:
                    resources = container.get("resources", {})
                    requests = resources.get("requests", {})
                    if not all(k in requests for k in ["cpu", "memory"]):
                        return False
        return True
    except Exception:
        return False

def check_project_quota(namespace: str, spec: Dict[str, Any]) -> bool:
    """检查项目配额"""
    try:
        project_name = spec.get("project")
        if not project_name:
            return False

        api = client.CustomObjectsApi()
        
        # 获取项目配额
        project = api.get_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural="projects",
            name=project_name
        )

        quotas = project.get("spec", {}).get("quotas", {})
        if not quotas:
            return False

        # 获取项目当前使用量
        current_jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"project={project_name}"
        )

        # 检查配额
        job_count = len(current_jobs.get("items", []))
        if job_count >= quotas.get("max_jobs", 0):
            return False

        return True
    except ApiException as e:
        if e.status == 404:  # Project not found
            return False
        raise
    except Exception:
        return False

# ===================== 内部辅助函数 =====================

def update_job_resources(job: Dict[str, Any], quotas: Dict[str, Any]) -> None:
    """更新Job资源配置"""
    # TODO: 实现Job资源更新逻辑
    pass

def update_project_permissions(project: Dict[str, Any], spec: Dict[str, Any]) -> None:
    """更新Project权限配置"""
    # TODO: 实现Project权限更新逻辑
    pass

def update_job_permissions(job: Dict[str, Any], spec: Dict[str, Any]) -> None:
    """更新Job权限配置"""
    # TODO: 实现Job权限更新逻辑
    pass 