"""配置管理"""

from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用配置"""
    # API配置
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Kubeflow Mini Backend"
    VERSION: str = "0.1.0"
    
    # 认证配置
    SECRET_KEY: str = "your-secret-key"  # TODO: 从环境变量读取
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # 数据库配置
    DATABASE_PROVIDER: str = "sqlite"
    DATABASE_FILENAME: str = "kubeflow_mini.db"
    DATABASE_HOST: Optional[str] = None
    DATABASE_PORT: Optional[int] = None
    DATABASE_USER: Optional[str] = None
    DATABASE_PASSWORD: Optional[str] = None
    DATABASE_NAME: Optional[str] = None
    
    # Kubernetes配置
    K8S_GROUP: str = "kubeflow-mini.io"
    K8S_VERSION: str = "v1"
    K8S_PLURAL: str = "mljobs"
    K8S_SYNC_INTERVAL: int = 30  # 状态同步间隔(秒)
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 