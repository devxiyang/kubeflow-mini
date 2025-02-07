"""数据库模型定义"""

from datetime import datetime
from typing import Optional
from pony.orm import Database, Required, Optional as PonyOptional, Set, PrimaryKey

db = Database()

class User(db.Entity):
    """用户模型"""
    username = Required(str, unique=True)
    email = Required(str)
    full_name = Required(str)
    hashed_password = Required(str)
    is_active = Required(bool, default=True)
    role = Required(str, default="user")  # user, admin
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    updated_at = Required(datetime, default=lambda: datetime.utcnow())
    
    # 关联
    projects = Set('Project')
    mljobs = Set('MLJob')

class Project(db.Entity):
    """项目模型"""
    name = Required(str, unique=True)
    description = PonyOptional(str)
    status = Required(str, default="active")  # active, archived, deleted
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    updated_at = Required(datetime, default=lambda: datetime.utcnow())
    
    # 配额设置
    gpu_limit = Required(int, default=0)
    cpu_limit = Required(float, default=0.0)
    memory_limit = Required(str, default="0")
    max_jobs = Required(int, default=0)
    
    # 关联
    owner = Required(User)
    mljobs = Set('MLJob')

class MLJob(db.Entity):
    """ML任务模型"""
    job_id = Required(str, unique=True)  # 业务ID,用于关联k8s资源
    name = Required(str)  # k8s资源名称
    namespace = Required(str, default="default")
    description = PonyOptional(str)
    priority = Required(int, default=0)  # 任务优先级 0-100
    labels = PonyOptional(str)  # 标签(JSON)
    
    # Training配置
    training = Required(str)  # training-operator配置(JSON)
    
    # 状态信息
    status = Required(str, default="pending")  # pending, running, succeeded, failed, deleted
    message = PonyOptional(str)  # 状态信息
    training_status = PonyOptional(str)  # training operator返回的状态(JSON)
    sync_errors = Required(int, default=0)  # 同步错误计数
    
    # 资源使用情况
    gpu_usage = PonyOptional(int)  # GPU使用量
    cpu_usage = PonyOptional(float)  # CPU使用量
    memory_usage = PonyOptional(str)  # 内存使用量
    
    # 时间信息
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    updated_at = Required(datetime, default=lambda: datetime.utcnow())
    started_at = PonyOptional(datetime)
    completed_at = PonyOptional(datetime)
    
    # 关联
    project = Required(Project)
    user = Required(User)

class Notebook(db.Entity):
    """Notebook实例"""
    id = PrimaryKey(int, auto=True)
    name = Required(str)
    description = Optional(str)
    image = Required(str)
    
    # 资源配额
    cpu_limit = Required(float)  # CPU核心数
    memory_limit = Required(str)  # 内存大小,如"2Gi"
    gpu_limit = Required(int)    # GPU数量
    
    # 状态信息
    status = Required(str, default="stopped")  # running, stopped
    message = Optional(str)      # 状态信息
    service_name = Optional(str) # Kubernetes service名称
    endpoint = Optional(str)     # 访问地址
    
    # 时间信息
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    updated_at = Required(datetime, default=lambda: datetime.utcnow())
    started_at = Optional(datetime)
    stopped_at = Optional(datetime)
    
    # 租约信息
    lease_status = Required(str, default="inactive")  # active, inactive, expired
    lease_start = Optional(datetime)  # 租约开始时间
    lease_duration = Required(int, default=24)  # 租约时长(小时)
    lease_renewal_count = Required(int, default=0)  # 续租次数
    max_lease_renewals = Required(int, default=3)  # 最大续租次数
    
    # 关联
    project = Required("Project")
    user = Required("User")
    
    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "image": self.image,
            "cpu_limit": self.cpu_limit,
            "memory_limit": self.memory_limit,
            "gpu_limit": self.gpu_limit,
            "status": self.status,
            "message": self.message,
            "service_name": self.service_name,
            "endpoint": self.endpoint,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "lease_status": self.lease_status,
            "lease_start": self.lease_start.isoformat() if self.lease_start else None,
            "lease_duration": self.lease_duration,
            "lease_renewal_count": self.lease_renewal_count,
            "max_lease_renewals": self.max_lease_renewals,
            "project_id": self.project.id,
            "user_id": self.user.id
        } 