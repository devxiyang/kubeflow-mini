"""数据库操作函数"""
from datetime import datetime
from pony.orm import db_session, select
from .models import MLJob, db

@db_session
def create_job(name, namespace, spec):
    """创建新任务"""
    distributed_config = spec.get('distributed', {})
    replica_specs = distributed_config.get('replicaSpecs', {})
    worker_spec = replica_specs.get('worker', {})
    ps_spec = replica_specs.get('ps', {})
    chief_spec = replica_specs.get('chief', {})

    return MLJob(
        name=name,
        namespace=namespace,
        framework=spec.get('framework'),
        framework_version=spec.get('frameworkVersion', ''),
        distributed=distributed_config.get('enabled', False),
        worker_replicas=worker_spec.get('replicas', 1),
        ps_replicas=ps_spec.get('replicas', 0),
        chief_replicas=chief_spec.get('replicas', 0),
        image=spec.get('image'),
        command=spec.get('command', []),
        args=spec.get('args', []),
        env=spec.get('env', []),
        resources=spec.get('resources', {}),
        status='created',
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

@db_session
def update_job_status(name, namespace, status, error_message=None):
    """更新任务状态"""
    job = MLJob.get(name=name, namespace=namespace)
    if job:
        job.status = status
        job.updated_at = datetime.now()
        if status in ['completed', 'failed']:
            job.completed_at = datetime.now()
        if error_message:
            job.error_message = error_message
        return job
    return None

@db_session
def delete_job(name, namespace):
    """删除任务"""
    job = MLJob.get(name=name, namespace=namespace)
    if job:
        job.status = 'deleted'
        job.updated_at = datetime.now()
        job.completed_at = datetime.now()
        return job
    return None

@db_session
def get_job(name, namespace):
    """获取任务信息"""
    return MLJob.get(name=name, namespace=namespace)

@db_session
def list_jobs(namespace=None, status=None, framework=None):
    """列出任务"""
    query = select(j for j in MLJob)
    if namespace:
        query = query.filter(lambda j: j.namespace == namespace)
    if status:
        query = query.filter(lambda j: j.status == status)
    if framework:
        query = query.filter(lambda j: j.framework == framework)
    return query[:]

def init_db(filename='jobs.sqlite'):
    """初始化数据库"""
    db.bind(provider='sqlite', filename=filename, create_db=True)
    db.generate_mapping(create_tables=True) 