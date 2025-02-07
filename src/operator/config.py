"""Operator配置"""

from typing import Dict
from pydantic import BaseSettings

class RetrySettings(BaseSettings):
    """重试配置"""
    max_attempts: int = 3
    initial_delay: int = 1
    max_delay: int = 300
    exponential_base: float = 2.0

class ReconcileSettings(BaseSettings):
    """调谐配置"""
    interval: int = 30  # 调谐间隔(秒)
    batch_size: int = 50  # 批处理大小
    timeout: int = 60  # 超时时间(秒)
    error_threshold: int = 3  # 错误阈值

class ResourceSettings(BaseSettings):
    """资源配置"""
    cleanup_interval: int = 3600  # 清理间隔(秒)
    max_age: int = 30  # 资源最大保留天数
    orphan_cleanup: bool = True  # 是否清理孤立资源

class Settings(BaseSettings):
    """Operator配置"""
    # API配置
    GROUP: str = "kubeflow-mini.io"
    VERSION: str = "v1"
    PLURAL: str = "mljobs"
    
    # Operator配置
    OPERATOR_NAME: str = "kubeflow-mini-operator"
    WATCH_NAMESPACE: str = ""  # 空字符串表示监听所有命名空间
    
    # Training Operator配置
    PYTORCH_GROUP: str = "kubeflow.org"
    PYTORCH_VERSION: str = "v1"
    PYTORCH_PLURAL: str = "pytorchjobs"
    
    TENSORFLOW_GROUP: str = "kubeflow.org"
    TENSORFLOW_VERSION: str = "v1"
    TENSORFLOW_PLURAL: str = "tfjobs"
    
    # 状态配置
    JOB_PHASES: Dict[str, str] = {
        "CREATED": "Created",
        "RUNNING": "Running", 
        "SUCCEEDED": "Succeeded",
        "FAILED": "Failed",
        "DELETED": "Deleted",
        "ERROR": "Error",
        "UNKNOWN": "Unknown"
    }
    
    # 重试配置
    RETRY: RetrySettings = RetrySettings()
    
    # 调谐配置
    RECONCILE: ReconcileSettings = ReconcileSettings()
    
    # 资源配置
    RESOURCE: ResourceSettings = ResourceSettings()
    
    # 标签配置
    LABELS: Dict[str, str] = {
        "app": "kubeflow-mini",
        "component": "mljob",
        "managed-by": "kubeflow-mini-operator"
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 