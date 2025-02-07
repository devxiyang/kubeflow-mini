"""配置管理"""

from typing import Optional
from pydantic_settings import BaseSettings

class RetrySettings(BaseSettings):
    """重试配置"""
    max_attempts: int = 3
    initial_delay: int = 1
    max_delay: int = 300
    exponential_base: float = 2.0

class ResourceSettings(BaseSettings):
    """资源配置"""
    cleanup_interval: int = 3600  # 资源清理间隔(秒)
    max_job_age: int = 30  # 已完成任务保留天数
    batch_size: int = 100  # 批处理大小

class NotebookSettings(BaseSettings):
    """Notebook配置"""
    default_lease_duration: int = 24  # 默认租约时长(小时)
    max_lease_duration: int = 168  # 最大租约时长(小时)
    default_max_renewals: int = 3  # 默认最大续租次数
    lease_check_interval: int = 300  # 租约检查间隔(秒)
    lease_warning_threshold: int = 3600  # 租约到期警告阈值(秒)

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
    
    # 重试配置
    RETRY: RetrySettings = RetrySettings()
    
    # 资源管理配置
    RESOURCE: ResourceSettings = ResourceSettings()
    
    # Notebook配置
    NOTEBOOK: NotebookSettings = NotebookSettings()
    
    # 状态同步配置
    SYNC_BATCH_SIZE: int = 50  # 每次同步的任务数量
    SYNC_ERROR_THRESHOLD: int = 3  # 错误阈值，超过后标记为失败
    SYNC_TIMEOUT: int = 60  # 同步超时时间(秒)
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings() 