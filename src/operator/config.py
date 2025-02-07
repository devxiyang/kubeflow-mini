"""Operator配置"""

from typing import Dict
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Operator配置"""
    # API配置
    GROUP: str = "kubeflow-mini.io"
    VERSION: str = "v1alpha1"
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
        "DELETED": "Deleted"
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings() 