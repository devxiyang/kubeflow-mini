"""数据库模型定义"""
from datetime import datetime
from pony.orm import *

db = Database()

class MLJob(db.Entity):
    """机器学习任务实体"""
    _table_ = 'ml_jobs'
    
    name = Required(str)
    namespace = Required(str)
    framework = Required(str)  # pytorch, tensorflow
    framework_version = Required(str)
    distributed = Required(bool, default=False)
    worker_replicas = Required(int, default=1)
    ps_replicas = Optional(int)  # Parameter Server replicas (for TensorFlow)
    image = Required(str)
    command = Optional(Json)
    args = Optional(Json)
    resources = Optional(Json)
    status = Required(str)  # created, running, completed, failed, deleted
    created_at = Required(datetime)
    updated_at = Required(datetime)
    completed_at = Optional(datetime)
    error_message = Optional(str)
    
    composite_key(name, namespace) 