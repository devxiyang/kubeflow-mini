"""Operator工具函数"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

# ===================== Training Job 操作 =====================

def get_k8s_api() -> client.CustomObjectsApi:
    """获取Kubernetes API客户端"""
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    return client.CustomObjectsApi()

def create_training_job(name: str, namespace: str, spec: Dict[str, Any], labels: Dict[str, str]) -> Dict[str, Any]:
    """创建Training Job
    
    Args:
        name: 资源名称
        namespace: 命名空间
        spec: MLJob规格
        labels: 资源标签
    
    Returns:
        Dict: 创建的资源对象
    """
    try:
        training = spec.get("training", {})
        if not training:
            raise ValueError("Training spec is required")
            
        api = get_k8s_api()
        
        # 准备Job配置
        job = {
            "apiVersion": training.get("api_version"),
            "kind": training.get("kind"),
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": labels
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
    
    Args:
        name: 资源名称
        namespace: 命名空间
        spec: MLJob规格
    """
    try:
        training = spec.get("training", {})
        if not training:
            return
            
        api = get_k8s_api()
        
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
    except ApiException as e:
        if e.status != 404:  # 忽略已删除的资源
            logger.error(f"Failed to delete training job: {str(e)}")
            raise
    except Exception as e:
        logger.error(f"Failed to delete training job: {str(e)}")
        raise

def get_training_job_status(name: str, namespace: str, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """获取Training Job状态
    
    Args:
        name: 资源名称
        namespace: 命名空间
        spec: MLJob规格
        
    Returns:
        Optional[Dict]: 资源状态，如果资源不存在返回None
    """
    try:
        training = spec.get("training", {})
        if not training:
            return None
            
        api = get_k8s_api()
        
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
    except ApiException as e:
        if e.status != 404:  # 忽略不存在的资源
            logger.error(f"Failed to get training job status: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Failed to get training job status: {str(e)}")
        raise

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
        api = get_k8s_api()
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
        api = get_k8s_api()
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
        api = get_k8s_api()
        
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
        api = get_k8s_api()
        
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

def should_cleanup_resource(job: Dict[str, Any]) -> bool:
    """检查资源是否需要清理
    
    检查条件:
    1. 资源年龄超过最大保留时间
    2. 资源状态为终态且超过保留时间
    3. 资源为孤立资源(如果启用孤立资源清理)
    """
    try:
        # 获取创建时间
        creation_time = job.get("metadata", {}).get("creationTimestamp")
        if not creation_time:
            return False
            
        age = datetime.utcnow() - datetime.fromisoformat(creation_time.rstrip("Z"))
        
        # 检查资源年龄
        if age.days > settings.RESOURCE.max_age:
            return True
            
        # 检查资源状态
        status = job.get("status", {})
        phase = status.get("phase")
        if phase in [settings.JOB_PHASES["SUCCEEDED"], 
                    settings.JOB_PHASES["FAILED"],
                    settings.JOB_PHASES["DELETED"]]:
            # 获取完成时间
            completion_time = status.get("completion_time")
            if completion_time:
                completed_age = datetime.utcnow() - datetime.fromisoformat(completion_time.rstrip("Z"))
                if completed_age.days > settings.RESOURCE.max_age:
                    return True
                    
        # 检查孤立资源
        if settings.RESOURCE.orphan_cleanup:
            # 检查关联的training job是否存在
            try:
                training = job.get("spec", {}).get("training", {})
                if training:
                    api_version = training.get("api_version", "").split("/")
                    if len(api_version) == 2:
                        api = get_k8s_api()
                        api.get_namespaced_custom_object(
                            group=api_version[0],
                            version=api_version[1],
                            namespace=job["metadata"]["namespace"],
                            plural=training.get("kind", "").lower() + "s",
                            name=job["metadata"]["name"]
                        )
                        return False  # 资源存在，不清理
            except ApiException as e:
                if e.status == 404:  # 资源不存在
                    return True
                    
        return False
    except Exception as e:
        logger.error(f"Error checking resource cleanup: {str(e)}")
        return False

def exponential_backoff(attempt: int, initial_delay: int = 1, 
                       max_delay: int = 300, base: float = 2.0) -> int:
    """计算指数退避延迟时间
    
    Args:
        attempt: 当前尝试次数
        initial_delay: 初始延迟时间(秒)
        max_delay: 最大延迟时间(秒)
        base: 指数基数
        
    Returns:
        int: 延迟时间(秒)
    """
    delay = min(initial_delay * (base ** attempt), max_delay)
    return int(delay)

def validate_resource_requests(spec: Dict[str, Any]) -> bool:
    """验证资源请求配置
    
    检查:
    1. CPU和内存请求是否合法
    2. GPU请求是否合法(如果有)
    """
    try:
        for replica_spec in spec.values():
            if isinstance(replica_spec, dict):
                template = replica_spec.get("template", {})
                containers = template.get("spec", {}).get("containers", [])
                for container in containers:
                    resources = container.get("resources", {})
                    requests = resources.get("requests", {})
                    
                    # 检查CPU
                    cpu = requests.get("cpu")
                    if cpu and not is_valid_cpu_value(cpu):
                        return False
                        
                    # 检查内存
                    memory = requests.get("memory")
                    if memory and not is_valid_memory_value(memory):
                        return False
                        
                    # 检查GPU
                    gpu = requests.get("nvidia.com/gpu")
                    if gpu and not is_valid_gpu_value(gpu):
                        return False
                        
        return True
    except Exception:
        return False

def is_valid_cpu_value(value: str) -> bool:
    """验证CPU值是否合法"""
    try:
        if value.endswith("m"):
            millicores = int(value[:-1])
            return 0 < millicores <= 256000  # 最大256核
        else:
            cores = float(value)
            return 0 < cores <= 256
    except:
        return False

def is_valid_memory_value(value: str) -> bool:
    """验证内存值是否合法"""
    try:
        units = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4}
        for unit, multiplier in units.items():
            if value.endswith(unit):
                amount = int(value[:-len(unit)])
                bytes = amount * multiplier
                return 0 < bytes <= 1024**4  # 最大1TB
        return False
    except:
        return False

def is_valid_gpu_value(value: str) -> bool:
    """验证GPU值是否合法"""
    try:
        count = int(value)
        return 0 <= count <= 16  # 最大16个GPU
    except:
        return False

def check_project_quota(namespace: str, spec: Dict[str, Any]) -> bool:
    """检查项目配额
    
    检查:
    1. 项目是否存在
    2. 项目配额是否足够
    """
    try:
        project_name = spec.get("project")
        if not project_name:
            return False

        api = get_k8s_api()
        
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