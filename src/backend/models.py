"""数据库模型定义"""

from datetime import datetime
from typing import Optional
from pony.orm import Database, Required, Optional as PonyOptional, Set

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
    """Notebook模型"""
    name = Required(str)
    description = PonyOptional(str)
    image = Required(str)  # notebook镜像
    status = Required(str, default="stopped")  # stopped, running, error
    message = PonyOptional(str)  # 状态信息
    
    # 资源配置
    gpu_limit = Required(int, default=0)
    cpu_limit = Required(float, default=1.0)
    memory_limit = Required(str, default="1Gi")
    
    # 运行信息
    service_name = PonyOptional(str)  # k8s service名称
    endpoint = PonyOptional(str)  # 访问地址
    
    # 时间信息
    created_at = Required(datetime, default=lambda: datetime.utcnow())
    updated_at = Required(datetime, default=lambda: datetime.utcnow())
    started_at = PonyOptional(datetime)
    stopped_at = PonyOptional(datetime)
    
    # 关联
    project = Required(Project)
    user = Required(User) 