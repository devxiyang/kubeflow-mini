"""Operator工具函数"""

import logging
from typing import Optional, Dict, Any
from kubernetes import client, config

from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

def create_training_job(name: str, namespace: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """创建Training Job"""
    try:
        # 获取Training配置
        training = spec.get("training", {})
        if not training:
            raise ValueError("Training spec is required")
            
        # 根据框架类型创建对应的Job
        kind = training.get("kind", "").lower()
        if "pytorch" in kind:
            return _create_pytorch_job(name, namespace, training)
        elif "tf" in kind:
            return _create_tensorflow_job(name, namespace, training)
        else:
            raise ValueError(f"Unsupported training kind: {kind}")
    except Exception as e:
        logger.error(f"Failed to create training job: {str(e)}")
        raise

def delete_training_job(name: str, namespace: str, spec: Dict[str, Any]) -> None:
    """删除Training Job"""
    try:
        # 获取Training配置
        training = spec.get("training", {})
        if not training:
            return
            
        # 根据框架类型删除对应的Job
        kind = training.get("kind", "").lower()
        if "pytorch" in kind:
            return _delete_pytorch_job(name, namespace)
        elif "tf" in kind:
            return _delete_tensorflow_job(name, namespace)
    except Exception as e:
        logger.error(f"Failed to delete training job: {str(e)}")
        raise

def get_training_job_status(name: str, namespace: str, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """获取Training Job状态"""
    try:
        # 获取Training配置
        training = spec.get("training", {})
        if not training:
            return None
            
        # 根据框架类型获取对应的Job状态
        kind = training.get("kind", "").lower()
        if "pytorch" in kind:
            return _get_pytorch_job_status(name, namespace)
        elif "tf" in kind:
            return _get_tensorflow_job_status(name, namespace)
        return None
    except Exception as e:
        logger.error(f"Failed to get training job status: {str(e)}")
        return None

def _create_pytorch_job(name: str, namespace: str, training: Dict[str, Any]) -> Dict[str, Any]:
    """创建PyTorch Job"""
    # 创建自定义资源API客户端
    api = client.CustomObjectsApi()
    
    # 准备Job配置
    job = {
        "apiVersion": f"{settings.PYTORCH_GROUP}/{settings.PYTORCH_VERSION}",
        "kind": "PyTorchJob",
        "metadata": {
            "name": name,
            "namespace": namespace
        },
        "spec": training.get("spec", {})
    }
    
    # 创建Job
    return api.create_namespaced_custom_object(
        group=settings.PYTORCH_GROUP,
        version=settings.PYTORCH_VERSION,
        namespace=namespace,
        plural=settings.PYTORCH_PLURAL,
        body=job
    )

def _create_tensorflow_job(name: str, namespace: str, training: Dict[str, Any]) -> Dict[str, Any]:
    """创建TensorFlow Job"""
    # 创建自定义资源API客户端
    api = client.CustomObjectsApi()
    
    # 准备Job配置
    job = {
        "apiVersion": f"{settings.TENSORFLOW_GROUP}/{settings.TENSORFLOW_VERSION}",
        "kind": "TFJob",
        "metadata": {
            "name": name,
            "namespace": namespace
        },
        "spec": training.get("spec", {})
    }
    
    # 创建Job
    return api.create_namespaced_custom_object(
        group=settings.TENSORFLOW_GROUP,
        version=settings.TENSORFLOW_VERSION,
        namespace=namespace,
        plural=settings.TENSORFLOW_PLURAL,
        body=job
    )

def _delete_pytorch_job(name: str, namespace: str) -> None:
    """删除PyTorch Job"""
    # 创建自定义资源API客户端
    api = client.CustomObjectsApi()
    
    # 删除Job
    api.delete_namespaced_custom_object(
        group=settings.PYTORCH_GROUP,
        version=settings.PYTORCH_VERSION,
        namespace=namespace,
        plural=settings.PYTORCH_PLURAL,
        name=name
    )

def _delete_tensorflow_job(name: str, namespace: str) -> None:
    """删除TensorFlow Job"""
    # 创建自定义资源API客户端
    api = client.CustomObjectsApi()
    
    # 删除Job
    api.delete_namespaced_custom_object(
        group=settings.TENSORFLOW_GROUP,
        version=settings.TENSORFLOW_VERSION,
        namespace=namespace,
        plural=settings.TENSORFLOW_PLURAL,
        name=name
    )

def _get_pytorch_job_status(name: str, namespace: str) -> Optional[Dict[str, Any]]:
    """获取PyTorch Job状态"""
    # 创建自定义资源API客户端
    api = client.CustomObjectsApi()
    
    try:
        # 获取Job
        job = api.get_namespaced_custom_object(
            group=settings.PYTORCH_GROUP,
            version=settings.PYTORCH_VERSION,
            namespace=namespace,
            plural=settings.PYTORCH_PLURAL,
            name=name
        )
        return job.get("status", {})
    except client.rest.ApiException as e:
        if e.status == 404:
            return None
        raise

def _get_tensorflow_job_status(name: str, namespace: str) -> Optional[Dict[str, Any]]:
    """获取TensorFlow Job状态"""
    # 创建自定义资源API客户端
    api = client.CustomObjectsApi()
    
    try:
        # 获取Job
        job = api.get_namespaced_custom_object(
            group=settings.TENSORFLOW_GROUP,
            version=settings.TENSORFLOW_VERSION,
            namespace=namespace,
            plural=settings.TENSORFLOW_PLURAL,
            name=name
        )
        return job.get("status", {})
    except client.rest.ApiException as e:
        if e.status == 404:
            return None
        raise 