"""Operator处理函数

该模块实现了MLJob资源的生命周期管理，包括：
1. 创建、更新、删除MLJob资源
2. 管理对应的training-operator任务
3. 监控和同步任务状态
4. 错误处理和重试机制
"""

import kopf
import logging
import kubernetes.client as k8s
from kubernetes.client.rest import ApiException
from datetime import datetime
from functools import wraps
import time

# 创建Kubernetes API客户端
api = k8s.CustomObjectsApi()

# 重试配置
RETRY_CONFIG = {
    'create': {'max_retries': 3, 'delay': 2},  # 创建操作重试配置
    'delete': {'max_retries': 5, 'delay': 1},  # 删除操作重试配置
    'update': {'max_retries': 3, 'delay': 2},  # 更新操作重试配置
    'get': {'max_retries': 3, 'delay': 1},     # 获取操作重试配置
}

class MLJobError(Exception):
    """MLJob操作异常基类
    
    用于区分MLJob特定的错误和其他系统错误
    """
    pass

class ResourceConflictError(MLJobError):
    """资源冲突错误
    
    当尝试创建已存在的资源或并发修改时抛出
    """
    pass

class ResourceNotFoundError(MLJobError):
    """资源不存在错误
    
    当尝试操作不存在的资源时抛出
    """
    pass

class InvalidSpecError(MLJobError):
    """无效的配置错误
    
    当资源配置不符合要求时抛出
    """
    pass

def retry_on_error(operation='default'):
    """重试装饰器
    
    Args:
        operation: 操作类型，用于获取对应的重试配置
        
    Returns:
        装饰器函数
        
    重试策略：
    1. 资源冲突(409): 临时错误，按配置重试
    2. 资源不存在(404): 直接抛出特定异常
    3. 其他API异常: 直接抛出
    4. 其他异常: 按配置重试
    """
    config = RETRY_CONFIG.get(operation, {'max_retries': 3, 'delay': 1})
    max_retries = config['max_retries']
    delay = config['delay']
    
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

@retry_on_error(operation='get')
def get_mljob(name, namespace, logger=None):
    """获取MLJob信息
    
    Args:
        name: MLJob名称
        namespace: 命名空间
        logger: 日志记录器
        
    Returns:
        MLJob资源对象，不存在时返回None
        
    Raises:
        ResourceNotFoundError: 资源不存在
        ApiException: 其他API错误
    """
    try:
        return api.get_namespaced_custom_object(
            group="kubeflow-mini.io",
            version="v1",
            namespace=namespace,
            plural="mljobs",
            name=name
        )
    except ApiException as e:
        if e.status == 404:
            return None
        raise

@retry_on_error(operation='get')
def get_training_job(training_spec, name, namespace, logger=None):
    """获取training-operator任务信息
    
    Args:
        training_spec: training-operator配置
        name: 任务名称
        namespace: 命名空间
        logger: 日志记录器
        
    Returns:
        Training Job资源对象，不存在时返回None
        
    Raises:
        ResourceNotFoundError: 资源不存在
        ApiException: 其他API错误
    """
    try:
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'
        return api.get_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=kind,
            name=name
        )
    except ApiException as e:
        if e.status == 404:
            return None
        raise

@retry_on_error(operation='create')
def create_training_job(name, namespace, training_spec, spec, logger=None):
    """创建training-operator任务
    
    Args:
        name: 任务名称
        namespace: 命名空间
        training_spec: training-operator配置
        spec: MLJob配置
        logger: 日志记录器
        
    Raises:
        InvalidSpecError: 配置无效
        ResourceConflictError: 资源已存在
        ApiException: 其他API错误
    """
    try:
        # 验证training_spec
        if not isinstance(training_spec, dict):
            raise InvalidSpecError("Training spec must be a dictionary")
        if 'apiVersion' not in training_spec or 'kind' not in training_spec:
            raise InvalidSpecError("Training spec must contain apiVersion and kind")

        # 从training_spec中获取API信息
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'

        # 设置training-operator任务的元数据
        training_spec['metadata'] = {
            'name': name,
            'namespace': namespace,
            'labels': {
                'mljob.kubeflow-mini.io/job-id': spec.get('jobId', ''),
                'mljob.kubeflow-mini.io/project': spec.get('project', ''),
                'mljob.kubeflow-mini.io/owner': spec.get('owner', '')
            },
            'annotations': {
                'mljob.kubeflow-mini.io/description': spec.get('description', ''),
                'mljob.kubeflow-mini.io/priority': str(spec.get('priority', 50)),
                'mljob.kubeflow-mini.io/tags': ','.join(spec.get('tags', []))
            }
        }

        # 检查任务是否已存在
        existing_job = get_training_job(training_spec, name, namespace, logger)
        if existing_job:
            raise ResourceConflictError(f"Training job {name} already exists")

        # 创建training-operator任务
        api.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=kind,
            body=training_spec
        )
        if logger:
            logger.info(f"Created training job: {name}")
    except ApiException as e:
        if e.status == 409:
            raise ResourceConflictError(f"Training job {name} already exists")
        raise

@retry_on_error(operation='delete')
def delete_training_job(name, namespace, training_spec, logger=None):
    """删除training-operator任务
    
    Args:
        name: 任务名称
        namespace: 命名空间
        training_spec: training-operator配置
        logger: 日志记录器
        
    Raises:
        ResourceNotFoundError: 资源不存在
        ApiException: 其他API错误
    """
    try:
        # 从training_spec中获取API信息
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'

        # 检查任务是否存在
        existing_job = get_training_job(training_spec, name, namespace, logger)
        if not existing_job:
            if logger:
                logger.warning(f"Training job {name} does not exist")
            return

        # 删除training-operator任务
        api.delete_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=kind,
            name=name
        )
        if logger:
            logger.info(f"Deleted training job: {name}")
    except ApiException as e:
        if e.status != 404:  # 忽略已经不存在的情况
            raise

@kopf.on.create('mljobs')
def create_ml_job(spec, name, namespace, logger, **kwargs):
    """处理新的机器学习任务创建
    
    Args:
        spec: MLJob配置
        name: 任务名称
        namespace: 命名空间
        logger: 日志记录器
        
    Returns:
        任务初始状态
        
    Raises:
        kopf.PermanentError: 永久性错误，不会重试
        kopf.TemporaryError: 临时性错误，会重试
    """
    try:
        # 验证必要字段
        if not spec:
            raise InvalidSpecError("Spec must be provided")
        
        training_spec = spec.get('training')
        if not training_spec:
            raise InvalidSpecError("Training spec must be provided")

        # 创建training-operator任务
        create_training_job(name, namespace, training_spec, spec, logger)
        logger.info(f"Successfully created ML job: {name}")

        # 返回初始状态
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'phase': 'Created',
                'startTime': current_time,
                'conditions': [{
                    'type': 'Created',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'JobCreated',
                    'message': 'Job was created successfully'
                }]
            }
        }

    except InvalidSpecError as e:
        logger.error(f"Invalid spec: {e}")
        raise kopf.PermanentError(str(e))
    except ResourceConflictError as e:
        logger.error(f"Resource conflict: {e}")
        raise kopf.TemporaryError(str(e), delay=10)
    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.delete('mljobs')
def delete_ml_job(spec, name, namespace, logger, **kwargs):
    """处理机器学习任务的删除
    
    Args:
        spec: MLJob配置
        name: 任务名称
        namespace: 命名空间
        logger: 日志记录器
        
    Returns:
        任务最终状态
    """
    try:
        training_spec = spec.get('training')
        if training_spec:
            # 删除training-operator任务
            delete_training_job(name, namespace, training_spec, logger)

        logger.info(f"Successfully deleted ML job: {name}")
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
        
    except ResourceNotFoundError:
        logger.warning(f"Job {name} not found, skipping deletion")
        return
    except Exception as e:
        logger.error(f"Failed to delete job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.update('mljobs')
def update_ml_job(spec, old, new, name, namespace, logger, **kwargs):
    """处理机器学习任务的更新
    
    Args:
        spec: 新的MLJob配置
        old: 旧的MLJob配置
        new: 新的MLJob完整配置
        name: 任务名称
        namespace: 命名空间
        logger: 日志记录器
        
    Returns:
        更新后的任务状态
        
    Raises:
        kopf.PermanentError: 永久性错误，不会重试
        kopf.TemporaryError: 临时性错误，会重试
    """
    try:
        # 验证新的spec
        if not spec:
            raise InvalidSpecError("Spec must be provided")
        
        training_spec = spec.get('training')
        if not training_spec:
            raise InvalidSpecError("Training spec must be provided")

        # 删除旧的training-operator任务
        old_training = old['spec'].get('training')
        if old_training:
            delete_training_job(name, namespace, old_training, logger)
            
        # 创建新的training-operator任务
        create_training_job(name, namespace, training_spec, spec, logger)

        logger.info(f"Successfully updated ML job: {name}")
        current_time = datetime.utcnow().isoformat() + "Z"
        return {
            'status': {
                'phase': 'Running',
                'conditions': [{
                    'type': 'Updated',
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': 'JobUpdated',
                    'message': 'Job was updated successfully'
                }]
            }
        }
    
    except InvalidSpecError as e:
        logger.error(f"Invalid spec: {e}")
        raise kopf.PermanentError(str(e))
    except ResourceConflictError as e:
        logger.error(f"Resource conflict: {e}")
        raise kopf.TemporaryError(str(e), delay=10)
    except Exception as e:
        logger.error(f"Failed to update job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.field('mljobs', field='status.phase')
def monitor_job_status(status, body, name, namespace, logger, **kwargs):
    """监控任务状态变化
    
    Args:
        status: 当前状态
        body: MLJob完整配置
        name: 任务名称
        namespace: 命名空间
        logger: 日志记录器
        
    Returns:
        更新后的状态信息
    """
    try:
        phase = status.get('phase', '').lower()
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # 获取开始时间
        start_time = body.get('status', {}).get('startTime')
        
        # 计算持续时间
        if start_time:
            try:
                start = datetime.fromisoformat(start_time.rstrip('Z'))
                current = datetime.utcnow()
                duration = str(current - start)
            except ValueError as e:
                logger.error(f"Invalid start time format: {e}")
                duration = None
        else:
            duration = None

        status_update = {
            'status': {
                'phase': phase.capitalize(),
                'duration': duration,
                'conditions': [{
                    'type': phase.capitalize(),
                    'status': 'True',
                    'lastTransitionTime': current_time,
                    'reason': f'Job{phase.capitalize()}',
                    'message': f'Job is {phase}'
                }]
            }
        }

        # 对于完成或失败的任务，添加完成时间
        if phase in ['succeeded', 'failed']:
            status_update['status']['completionTime'] = current_time

        return status_update
                
    except Exception as e:
        logger.error(f"Error monitoring job status: {e}")
        # 状态监控错误不应该影响任务运行
        return None 