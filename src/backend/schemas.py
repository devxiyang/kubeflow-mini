"""API Schema定义"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr

# ... 其他现有schema保持不变 ...

class NotebookBase(BaseModel):
    """Notebook基础模型"""
    name: str
    description: Optional[str] = None
    image: str
    gpu_limit: int = 0
    cpu_limit: float = 1.0
    memory_limit: str = "1Gi"
    lease_duration: Optional[int] = 24  # 租约时长(小时)
    max_lease_renewals: Optional[int] = 3  # 最大续租次数

class NotebookCreate(NotebookBase):
    """创建Notebook请求"""
    project_id: int

class NotebookUpdate(BaseModel):
    """更新Notebook请求"""
    description: Optional[str] = None
    gpu_limit: Optional[int] = None
    cpu_limit: Optional[float] = None
    memory_limit: Optional[str] = None
    lease_duration: Optional[int] = None
    max_lease_renewals: Optional[int] = None

class Notebook(NotebookBase):
    """Notebook响应"""
    id: int
    status: str
    message: Optional[str] = None
    service_name: Optional[str] = None
    endpoint: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    lease_status: str
    lease_start: Optional[datetime] = None
    lease_renewal_count: int = 0
    project_id: int
    user_id: int

    class Config:
        from_attributes = True 