"""Kubernetes资源操作"""

import logging
from typing import Dict, Any
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from fastapi import HTTPException

from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

# 初始化k8s客户端
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

# API客户端
core_api = client.CoreV1Api()
apps_api = client.AppsV1Api()

def create_namespace(name: str, labels: Dict[str, str] = None):
    """创建Kubernetes namespace"""
    try:
        body = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": name,
                "labels": {
                    "created-by": "kubeflow-mini",
                    **(labels or {})
                }
            }
        }
        
        core_api.create_namespace(body=body)
        
        # 创建资源配额
        quota = {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {
                "name": f"{name}-quota",
                "namespace": name
            },
            "spec": {
                "hard": {
                    "requests.cpu": "0",
                    "requests.memory": "0",
                    "requests.nvidia.com/gpu": "0",
                    "limits.cpu": "0",
                    "limits.memory": "0",
                    "limits.nvidia.com/gpu": "0"
                }
            }
        }
        
        core_api.create_namespaced_resource_quota(
            namespace=name,
            body=quota
        )
        
    except ApiException as e:
        logger.error(f"Failed to create namespace {name}: {str(e)}")
        raise

def update_namespace_quota(name: str, cpu_limit: float, memory_limit: str, gpu_limit: int):
    """更新namespace的资源配额"""
    try:
        quota = {
            "apiVersion": "v1",
            "kind": "ResourceQuota",
            "metadata": {
                "name": f"{name}-quota",
                "namespace": name
            },
            "spec": {
                "hard": {
                    "requests.cpu": str(cpu_limit/2),  # 请求设为限制的一半
                    "requests.memory": _halve_memory(memory_limit),
                    "requests.nvidia.com/gpu": str(gpu_limit),
                    "limits.cpu": str(cpu_limit),
                    "limits.memory": memory_limit,
                    "limits.nvidia.com/gpu": str(gpu_limit)
                }
            }
        }
        
        core_api.replace_namespaced_resource_quota(
            name=f"{name}-quota",
            namespace=name,
            body=quota
        )
        
    except ApiException as e:
        logger.error(f"Failed to update namespace quota for {name}: {str(e)}")
        raise

def delete_namespace(name: str):
    """删除Kubernetes namespace"""
    try:
        core_api.delete_namespace(name=name)
    except ApiException as e:
        if e.status != 404:  # 忽略不存在的资源
            logger.error(f"Failed to delete namespace {name}: {str(e)}")
            raise

def get_namespace_quota(name: str) -> Dict[str, Any]:
    """获取namespace的资源配额使用情况"""
    try:
        quota = core_api.read_namespaced_resource_quota(
            name=f"{name}-quota",
            namespace=name
        )
        
        status = quota.status
        if not status:
            return {}
            
        return {
            "cpu": {
                "used": _parse_cpu(status.used.get("requests.cpu", "0")),
                "limit": _parse_cpu(status.hard.get("limits.cpu", "0"))
            },
            "memory": {
                "used": status.used.get("requests.memory", "0"),
                "limit": status.hard.get("limits.memory", "0")
            },
            "gpu": {
                "used": int(status.used.get("requests.nvidia.com/gpu", "0")),
                "limit": int(status.hard.get("limits.nvidia.com/gpu", "0"))
            }
        }
        
    except ApiException as e:
        if e.status != 404:  # 忽略不存在的资源
            logger.error(f"Failed to get namespace quota for {name}: {str(e)}")
        return {}

def _parse_cpu(cpu_str: str) -> float:
    """解析CPU值为浮点数"""
    try:
        if cpu_str.endswith("m"):
            return float(cpu_str[:-1]) / 1000
        return float(cpu_str)
    except:
        return 0.0

def _halve_memory(memory: str) -> str:
    """将内存限制减半"""
    try:
        # 解析内存字符串
        if memory.endswith("Gi"):
            value = float(memory[:-2]) / 2
            return f"{value}Gi"
        elif memory.endswith("Mi"):
            value = float(memory[:-2]) / 2
            return f"{value}Mi"
        elif memory.endswith("Ki"):
            value = float(memory[:-2]) / 2
            return f"{value}Ki"
        return memory
    except:
        return memory

def create_notebook_resources(name: str, namespace: str, spec: Dict[str, Any]) -> None:
    """创建Notebook相关的Kubernetes资源
    
    Args:
        name: Notebook名称
        namespace: 项目namespace
        spec: Notebook配置
    """
    try:
        # 创建deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "replicas": 1,
                "selector": {
                    "matchLabels": {
                        "app": name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name
                        }
                    },
                    "spec": {
                        "containers": [{
                            "name": "notebook",
                            "image": spec["image"],
                            "ports": [{
                                "containerPort": 8888
                            }],
                            "resources": spec["resources"]
                        }]
                    }
                }
            }
        }
        
        apps_api.create_namespaced_deployment(
            namespace=namespace,
            body=deployment
        )
        
        # 创建service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": namespace
            },
            "spec": {
                "selector": {
                    "app": name
                },
                "ports": [{
                    "port": 8888,
                    "targetPort": 8888
                }],
                "type": "ClusterIP"
            }
        }
        
        core_api.create_namespaced_service(
            namespace=namespace,
            body=service
        )
        
    except ApiException as e:
        logger.error(f"Failed to create notebook resources: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create notebook resources: {str(e)}"
        )

def update_notebook_resources(name: str, namespace: str, spec: Dict[str, Any]):
    """更新Notebook相关的Kubernetes资源"""
    try:
        # 更新Deployment
        deployment = apps_api.read_namespaced_deployment(
            name=name,
            namespace=namespace
        )
        
        # 更新容器配置
        deployment.spec.template.spec.containers[0].resources = spec["resources"]
        
        apps_api.patch_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=deployment
        )
        
    except ApiException as e:
        logger.error(f"Failed to update Kubernetes resources: {str(e)}")
        raise

def delete_notebook_resources(name: str, namespace: str) -> None:
    """删除Notebook相关的Kubernetes资源
    
    Args:
        name: Notebook名称
        namespace: 项目namespace
    """
    try:
        # 删除deployment
        apps_api.delete_namespaced_deployment(
            name=name,
            namespace=namespace
        )
        
        # 删除service
        core_api.delete_namespaced_service(
            name=name,
            namespace=namespace
        )
        
    except ApiException as e:
        if e.status != 404:  # 忽略404错误
            logger.error(f"Failed to delete notebook resources: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete notebook resources: {str(e)}"
            )

def get_notebook_endpoint(name: str, namespace: str) -> str:
    """获取Notebook访问地址
    
    Args:
        name: Notebook名称
        namespace: 项目namespace
        
    Returns:
        访问地址
    """
    try:
        service = core_api.read_namespaced_service(
            name=name,
            namespace=namespace
        )
        
        # 获取service的cluster ip
        cluster_ip = service.spec.cluster_ip
        
        # 构建访问地址
        return f"http://{cluster_ip}:8888"
        
    except ApiException as e:
        logger.error(f"Failed to get notebook endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get notebook endpoint: {str(e)}"
        )

def create_mljob_resource(name: str, namespace: str, job_id: str, spec: Dict[str, Any]):
    """创建MLJob资源"""
    try:
        body = {
            "apiVersion": f"{settings.K8S_GROUP}/{settings.K8S_VERSION}",
            "kind": "MLJob",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {
                    "app": "kubeflow-mini",
                    "component": "mljob",
                    "job-id": job_id,
                    "created-by": "kubeflow-mini"
                }
            },
            "spec": spec
        }
        
        return client.CustomObjectsApi().create_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural=settings.K8S_PLURAL,
            body=body
        )
    except ApiException as e:
        logger.error(f"Failed to create MLJob resource: {str(e)}")
        raise

def update_mljob_resource(name: str, namespace: str, spec: Dict[str, Any]):
    """更新MLJob资源"""
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
        
        return client.CustomObjectsApi().patch_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural=settings.K8S_PLURAL,
            name=name,
            body=body
        )
    except ApiException as e:
        logger.error(f"Failed to update MLJob resource: {str(e)}")
        raise

def delete_mljob_resource(name: str, namespace: str):
    """删除MLJob资源"""
    try:
        client.CustomObjectsApi().delete_namespaced_custom_object(
            group=settings.K8S_GROUP,
            version=settings.K8S_VERSION,
            namespace=namespace,
            plural=settings.K8S_PLURAL,
            name=name
        )
    except ApiException as e:
        if e.status != 404:  # 忽略不存在的资源
            logger.error(f"Failed to delete MLJob resource: {str(e)}")
            raise 