"""Project资源处理器

该模块负责处理Project资源的生命周期管理，包括：
1. 创建和更新Project
2. 管理资源配额
3. 跟踪资源使用情况
4. 验证和强制执行配额限制
"""

import kopf
import logging
from kubernetes.client.rest import ApiException
from datetime import datetime
from .handlers import retry_on_error, ResourceNotFoundError, ResourceConflictError
from ..config import config

API_CONFIG = config.get_api_config()

@kopf.on.create('projects')
def create_project(spec, name, logger, **kwargs):
    """处理Project创建
    
    1. 验证项目配置
    2. 初始化资源使用统计
    3. 设置初始状态
    """
    try:
        # 验证配额设置
        validate_quota(spec.get('quota', {}))
        
        # 返回初始状态
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'phase': 'Active',
                'usage': {
                    'gpu': 0,
                    'cpu': '0',
                    'memory': '0',
                    'storage': '0',
                    'currentJobs': 0
                },
                'conditions': [{
                    'type': 'Created',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'ProjectCreated',
                    'message': 'Project was created successfully'
                }]
            }
        }
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.update('projects')
def update_project(spec, old, new, name, logger, **kwargs):
    """处理Project更新
    
    1. 验证新的配额设置
    2. 检查是否违反现有资源使用
    3. 更新状态
    """
    try:
        # 验证新的配额设置
        new_quota = spec.get('quota', {})
        validate_quota(new_quota)
        
        # 检查现有资源使用是否超过新配额
        current_usage = old.get('status', {}).get('usage', {})
        if violates_quota(current_usage, new_quota):
            raise kopf.PermanentError(
                "New quota would violate current resource usage"
            )
        
        # 返回更新状态
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'conditions': [{
                    'type': 'Updated',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'ProjectUpdated',
                    'message': 'Project was updated successfully'
                }]
            }
        }
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.delete('projects')
def delete_project(spec, name, logger, **kwargs):
    """处理Project删除
    
    1. 检查是否还有运行中的任务
    2. 清理相关资源
    """
    try:
        # 检查是否有关联的MLJob
        if has_active_jobs(name):
            raise kopf.PermanentError(
                "Cannot delete project with active jobs"
            )
        
        # 返回最终状态
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'phase': 'Terminated',
                'conditions': [{
                    'type': 'Deleted',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'ProjectDeleted',
                    'message': 'Project was deleted successfully'
                }]
            }
        }
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise kopf.PermanentError(str(e))

def validate_quota(quota):
    """验证配额设置的有效性"""
    if not quota:
        return
    
    # 验证GPU配额
    gpu = quota.get('gpu', {})
    if gpu:
        limit = gpu.get('limit', 0)
        request = gpu.get('request', 0)
        if request > limit:
            raise ValueError("GPU request cannot exceed limit")
    
    # 验证CPU配额
    cpu = quota.get('cpu', {})
    if cpu:
        limit = parse_cpu(cpu.get('limit', '0'))
        request = parse_cpu(cpu.get('request', '0'))
        if request > limit:
            raise ValueError("CPU request cannot exceed limit")
    
    # 验证内存配额
    memory = quota.get('memory', {})
    if memory:
        limit = parse_memory(memory.get('limit', '0'))
        request = parse_memory(memory.get('request', '0'))
        if request > limit:
            raise ValueError("Memory request cannot exceed limit")
    
    # 验证存储配额
    storage = quota.get('storage', {})
    if storage:
        limit = parse_memory(storage.get('limit', '0'))
        request = parse_memory(storage.get('request', '0'))
        if request > limit:
            raise ValueError("Storage request cannot exceed limit")

def violates_quota(usage, quota):
    """检查资源使用是否违反配额限制"""
    if not quota:
        return False
    
    # 检查GPU使用
    if 'gpu' in quota and 'gpu' in usage:
        if usage['gpu'] > quota['gpu'].get('limit', 0):
            return True
    
    # 检查CPU使用
    if 'cpu' in quota and 'cpu' in usage:
        usage_cpu = parse_cpu(usage['cpu'])
        limit_cpu = parse_cpu(quota['cpu'].get('limit', '0'))
        if usage_cpu > limit_cpu:
            return True
    
    # 检查内存使用
    if 'memory' in quota and 'memory' in usage:
        usage_mem = parse_memory(usage['memory'])
        limit_mem = parse_memory(quota['memory'].get('limit', '0'))
        if usage_mem > limit_mem:
            return True
    
    # 检查存储使用
    if 'storage' in quota and 'storage' in usage:
        usage_storage = parse_memory(usage['storage'])
        limit_storage = parse_memory(quota['storage'].get('limit', '0'))
        if usage_storage > limit_storage:
            return True
    
    # 检查任务数量
    if 'maxJobs' in quota and 'currentJobs' in usage:
        if usage['currentJobs'] > quota['maxJobs']:
            return True
    
    return False

def parse_cpu(cpu_str):
    """解析CPU数值（支持m单位）"""
    if not cpu_str:
        return 0
    if cpu_str.endswith('m'):
        return float(cpu_str[:-1]) / 1000
    return float(cpu_str)

def parse_memory(memory_str):
    """解析内存/存储数值（支持Ki/Mi/Gi等单位）"""
    if not memory_str:
        return 0
    
    units = {
        'Ki': 2**10,
        'Mi': 2**20,
        'Gi': 2**30,
        'Ti': 2**40,
        'Pi': 2**50,
        'Ei': 2**60,
        'K': 10**3,
        'M': 10**6,
        'G': 10**9,
        'T': 10**12,
        'P': 10**15,
        'E': 10**18
    }
    
    for unit, multiplier in units.items():
        if memory_str.endswith(unit):
            return float(memory_str[:-len(unit)]) * multiplier
    return float(memory_str)

@retry_on_error(operation='get')
def has_active_jobs(project_id):
    """检查项目是否有活动的任务"""
    try:
        api = kopf.CustomObjectsApi()
        jobs = api.list_cluster_custom_object(
            group=API_CONFIG['group'],
            version=API_CONFIG['version'],
            plural='mljobs',
            label_selector=f"kubeflow-mini.io/project={project_id}"
        )
        
        active_phases = {'Created', 'Running'}
        return any(
            job.get('status', {}).get('phase') in active_phases
            for job in jobs.get('items', [])
        )
    except ApiException as e:
        if e.status == 404:
            return False
        raise 