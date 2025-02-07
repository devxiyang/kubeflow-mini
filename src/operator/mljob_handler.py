"""MLJob处理器

该模块负责处理MLJob资源的生命周期管理，包括：
1. 验证Project和Owner关联
2. 检查资源配额
3. 创建和管理Training Job
4. 更新资源使用统计
"""

import kopf
import logging
from kubernetes.client.rest import ApiException
from datetime import datetime
from functools import wraps
import time
from .handlers import (
    retry_on_error, ResourceNotFoundError, ResourceConflictError, InvalidSpecError
)
from .project_handler import parse_cpu, parse_memory, violates_quota
from ..config import config

# 创建Kubernetes API客户端
api = kopf.CustomObjectsApi()

# 获取API配置
API_CONFIG = config.get_api_config()

# 异常类定义
class MLJobError(Exception):
    """MLJob操作异常基类"""
    pass

class ResourceConflictError(MLJobError):
    """资源冲突错误"""
    pass

class ResourceNotFoundError(MLJobError):
    """资源不存在错误"""
    pass

class InvalidSpecError(MLJobError):
    """无效的配置错误"""
    pass

# 重试装饰器
def retry_on_error(operation='default'):
    """重试装饰器
    
    Args:
        operation: 操作类型，用于获取对应的重试配置
        
    Returns:
        装饰器函数
    """
    retry_config = config.get_retry_config(operation)
    max_retries = retry_config.get('max_retries', 3)
    delay = retry_config.get('delay', 1)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, logger=None, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, logger=logger, **kwargs)
                except ApiException as e:
                    last_exception = e
                    if e.status == 409:  # Conflict
                        if logger:
                            logger.warning(
                                f"资源冲突，操作[{operation}]重试 "
                                f"{attempt + 1}/{max_retries}"
                            )
                        time.sleep(delay * (attempt + 1))  # 指数退避
                    elif e.status == 404:  # Not Found
                        raise ResourceNotFoundError(f"资源不存在: {str(e)}")
                    else:
                        raise
                except Exception as e:
                    last_exception = e
                    if logger:
                        logger.error(
                            f"操作[{operation}]失败，重试 "
                            f"{attempt + 1}/{max_retries}: {e}"
                        )
                    time.sleep(delay * (attempt + 1))  # 指数退避
            
            # 所有重试都失败后，抛出最后一个异常
            if isinstance(last_exception, ApiException):
                if last_exception.status == 409:
                    raise ResourceConflictError(
                        f"资源冲突且重试{max_retries}次后仍失败: {str(last_exception)}"
                    )
            raise last_exception
        return wrapper
    return decorator

# MLJob处理函数
@kopf.on.create('mljobs')
def create_mljob(spec, name, namespace, logger, **kwargs):
    """处理MLJob创建
    
    1. 验证Project和Owner关联
    2. 检查资源配额
    3. 创建Training Job
    4. 更新Project资源使用
    """
    try:
        # 验证关联
        project_id = spec.get('projectRef')
        owner_name = spec.get('ownerRef')
        if not project_id or not owner_name:
            raise InvalidSpecError("Project and Owner references are required")
        
        # 验证Project和Owner
        project = validate_project(project_id)
        owner = validate_owner(owner_name)
        
        # 计算资源需求
        resource_request = calculate_resource_request(spec['training'])
        
        # 检查配额
        project_quota = project['spec'].get('quota', {})
        current_usage = project['status'].get('usage', {})
        if violates_quota(
            {**current_usage, **resource_request},
            project_quota
        ):
            raise kopf.PermanentError("Resource quota exceeded")
        
        # 创建Training Job
        training_spec = spec.get('training')
        if not training_spec:
            raise InvalidSpecError("Training spec must be provided")
        
        # 设置Training Job的元数据
        training_spec['metadata'] = {
            'name': name,
            'namespace': namespace,
            'labels': {
                'kubeflow-mini.io/job-id': spec.get('jobId', ''),
                'kubeflow-mini.io/project': project_id,
                'kubeflow-mini.io/owner': owner_name,
                'kubeflow-mini.io/department': owner['spec']['department']
            }
        }
        
        # 创建Training Job
        api = kopf.CustomObjectsApi()
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'
        api.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=kind,
            body=training_spec
        )
        
        # 更新Project资源使用
        update_project_usage(project_id, resource_request, 1)
        
        # 返回初始状态
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'phase': 'Created',
                'startTime': current_time,
                'resourceUsage': resource_request,
                'conditions': [{
                    'type': 'Created',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'JobCreated',
                    'message': 'Job was created successfully'
                }]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.delete('mljobs')
def delete_mljob(spec, status, name, namespace, logger, **kwargs):
    """处理MLJob删除
    
    1. 删除Training Job
    2. 更新Project资源使用
    """
    try:
        # 删除Training Job
        training_spec = spec.get('training')
        if training_spec:
            api = kopf.CustomObjectsApi()
            group, version = training_spec['apiVersion'].split('/')
            kind = training_spec['kind'].lower() + 's'
            try:
                api.delete_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=kind,
                    name=name
                )
            except ApiException as e:
                if e.status != 404:  # 忽略已经不存在的情况
                    raise
        
        # 更新Project资源使用
        project_id = spec.get('projectRef')
        if project_id:
            resource_usage = status.get('resourceUsage', {})
            update_project_usage(project_id, resource_usage, -1)
        
        # 返回最终状态
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'phase': 'Deleted',
                'completionTime': current_time,
                'conditions': [{
                    'type': 'Deleted',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'JobDeleted',
                    'message': 'Job was deleted successfully'
                }]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to delete job: {e}")
        raise kopf.PermanentError(str(e))

# 辅助函数
@retry_on_error(operation='get')
def validate_project(project_id):
    """验证Project是否存在且处于活动状态"""
    api = kopf.CustomObjectsApi()
    try:
        project = api.get_cluster_custom_object(
            group=API_CONFIG['group'],
            version=API_CONFIG['version'],
            plural='projects',
            name=project_id
        )
        
        if project['status'].get('phase') != 'Active':
            raise kopf.PermanentError(f"Project {project_id} is not active")
        
        return project
    except ApiException as e:
        if e.status == 404:
            raise kopf.PermanentError(f"Project {project_id} does not exist")
        raise

@retry_on_error(operation='get')
def validate_owner(owner_name):
    """验证Owner是否存在"""
    api = kopf.CustomObjectsApi()
    try:
        owner = api.get_cluster_custom_object(
            group=API_CONFIG['group'],
            version=API_CONFIG['version'],
            plural='owners',
            name=owner_name
        )
        return owner
    except ApiException as e:
        if e.status == 404:
            raise kopf.PermanentError(f"Owner {owner_name} does not exist")
        raise

def calculate_resource_request(training_spec):
    """计算Training Job的资源需求"""
    resource_request = {
        'gpu': 0,
        'cpu': '0',
        'memory': '0',
        'storage': '0'
    }
    
    # 遍历所有replica类型
    for replica_spec in training_spec.get('spec', {}).values():
        if not isinstance(replica_spec, dict):
            continue
            
        replicas = replica_spec.get('replicas', 1)
        containers = replica_spec.get('template', {}).get('spec', {}).get('containers', [])
        
        # 累加每个容器的资源请求
        for container in containers:
            resources = container.get('resources', {}).get('requests', {})
            
            # GPU
            gpu = resources.get('nvidia.com/gpu', 0)
            resource_request['gpu'] += int(gpu) * replicas
            
            # CPU
            cpu = resources.get('cpu', '0')
            resource_request['cpu'] = str(
                parse_cpu(resource_request['cpu']) + 
                parse_cpu(cpu) * replicas
            )
            
            # Memory
            memory = resources.get('memory', '0')
            resource_request['memory'] = str(
                parse_memory(resource_request['memory']) + 
                parse_memory(memory) * replicas
            )
            
            # Storage (如果有PVC配置)
            storage = resources.get('ephemeral-storage', '0')
            resource_request['storage'] = str(
                parse_memory(resource_request['storage']) + 
                parse_memory(storage) * replicas
            )
    
    return resource_request

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

@retry_on_error(operation='patch')
def update_project_usage(project_id, resource_delta, jobs_delta):
    """更新Project的资源使用统计
    
    Args:
        project_id: Project ID
        resource_delta: 资源变化量
        jobs_delta: 任务数量变化 (+1 或 -1)
    """
    api = kopf.CustomObjectsApi()
    try:
        project = api.get_cluster_custom_object(
            group=API_CONFIG['group'],
            version=API_CONFIG['version'],
            plural='projects',
            name=project_id
        )
        
        current_usage = project['status'].get('usage', {})
        new_usage = {
            'gpu': current_usage.get('gpu', 0) + resource_delta.get('gpu', 0),
            'cpu': str(
                parse_cpu(current_usage.get('cpu', '0')) + 
                parse_cpu(resource_delta.get('cpu', '0'))
            ),
            'memory': str(
                parse_memory(current_usage.get('memory', '0')) + 
                parse_memory(resource_delta.get('memory', '0'))
            ),
            'storage': str(
                parse_memory(current_usage.get('storage', '0')) + 
                parse_memory(resource_delta.get('storage', '0'))
            ),
            'currentJobs': current_usage.get('currentJobs', 0) + jobs_delta
        }
        
        # 更新Project状态
        api.patch_cluster_custom_object_status(
            group=API_CONFIG['group'],
            version=API_CONFIG['version'],
            plural='projects',
            name=project_id,
            body={'status': {'usage': new_usage}}
        )
        
    except ApiException as e:
        if e.status == 404:
            raise kopf.PermanentError(f"Project {project_id} does not exist")
        raise 