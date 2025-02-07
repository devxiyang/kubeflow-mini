"""Kubernetes资源操作"""

import logging
from typing import Dict, Any
from kubernetes import client, config
from kubernetes.client.rest import ApiException

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

def create_notebook_resources(name: str, namespace: str, spec: Dict[str, Any]):
    """创建Notebook相关的Kubernetes资源
    
    创建:
    1. Deployment - 运行Notebook服务器
    2. Service - 暴露Notebook服务
    """
    try:
        # 1. 创建Deployment
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {
                    "app": name,
                    "component": "notebook",
                    "created-by": "kubeflow-mini"
                }
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
                                "containerPort": 8888,
                                "name": "notebook"
                            }],
                            "resources": spec["resources"],
                            "env": [
                                {
                                    "name": "JUPYTER_ENABLE_LAB",
                                    "value": "yes"
                                }
                            ]
                        }]
                    }
                }
            }
        }
        
        apps_api.create_namespaced_deployment(
            namespace=namespace,
            body=deployment
        )
        
        # 2. 创建Service
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "labels": {
                    "app": name,
                    "component": "notebook",
                    "created-by": "kubeflow-mini"
                }
            },
            "spec": {
                "type": "ClusterIP",
                "ports": [{
                    "port": 8888,
                    "targetPort": 8888,
                    "protocol": "TCP",
                    "name": "notebook"
                }],
                "selector": {
                    "app": name
                }
            }
        }
        
        core_api.create_namespaced_service(
            namespace=namespace,
            body=service
        )
        
    except ApiException as e:
        logger.error(f"Failed to create Kubernetes resources: {str(e)}")
        raise

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

def delete_notebook_resources(name: str, namespace: str):
    """删除Notebook相关的Kubernetes资源"""
    try:
        # 删除Deployment
        try:
            apps_api.delete_namespaced_deployment(
                name=name,
                namespace=namespace
            )
        except ApiException as e:
            if e.status != 404:  # 忽略不存在的资源
                raise
                
        # 删除Service
        try:
            core_api.delete_namespaced_service(
                name=name,
                namespace=namespace
            )
        except ApiException as e:
            if e.status != 404:  # 忽略不存在的资源
                raise
                
    except ApiException as e:
        logger.error(f"Failed to delete Kubernetes resources: {str(e)}")
        raise

def get_notebook_endpoint(name: str, namespace: str) -> str:
    """获取Notebook访问地址"""
    try:
        service = core_api.read_namespaced_service(
            name=name,
            namespace=namespace
        )
        
        # 根据实际环境构建访问地址
        if service.spec.type == "LoadBalancer" and service.status.load_balancer.ingress:
            host = service.status.load_balancer.ingress[0].ip or service.status.load_balancer.ingress[0].hostname
            return f"http://{host}:8888"
        else:
            # 使用集群内部地址
            return f"http://{service.metadata.name}.{service.metadata.namespace}.svc:8888"
            
    except ApiException as e:
        logger.error(f"Failed to get notebook endpoint: {str(e)}")
        return "" 