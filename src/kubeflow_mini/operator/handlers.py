"""Operator处理函数"""
import kopf
import logging
import kubernetes.client as k8s
from kubernetes.client.rest import ApiException

# 创建Kubernetes API客户端
api = k8s.CustomObjectsApi()

def get_mljob(name, namespace):
    """获取MLJob信息"""
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
        raise e

def get_training_job(training_spec, name, namespace):
    """获取training-operator任务信息"""
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
        raise e

def create_training_job(name, namespace, training_spec, logger):
    """创建training-operator任务"""
    try:
        # 从training_spec中获取API信息
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'  # 转换为复数形式作为plural

        # 设置training-operator任务的元数据
        training_spec['metadata'] = {
            'name': name,
            'namespace': namespace
        }

        # 创建training-operator任务
        api.create_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=kind,
            body=training_spec
        )
        logger.info(f"Created training job: {name}")
    except ApiException as e:
        logger.error(f"Failed to create training job: {e}")
        raise kopf.PermanentError(str(e))

def delete_training_job(name, namespace, training_spec, logger):
    """删除training-operator任务"""
    try:
        # 从training_spec中获取API信息
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'  # 转换为复数形式作为plural

        # 删除training-operator任务
        api.delete_namespaced_custom_object(
            group=group,
            version=version,
            namespace=namespace,
            plural=kind,
            name=name
        )
        logger.info(f"Deleted training job: {name}")
    except ApiException as e:
        if e.status != 404:  # 忽略已经不存在的情况
            logger.error(f"Failed to delete training job: {e}")
            raise kopf.PermanentError(str(e))

@kopf.on.create('mljobs')
def create_ml_job(spec, name, namespace, logger, **kwargs):
    """处理新的机器学习任务创建"""
    try:
        training_spec = spec.get('training')
        if not training_spec:
            raise kopf.PermanentError("Training spec must be provided")

        # 创建training-operator任务
        create_training_job(name, namespace, training_spec, logger)
        logger.info(f"Successfully created ML job: {name}")

        # 返回初始状态
        return {
            'status': {
                'phase': 'Created',
                'conditions': [{
                    'type': 'Created',
                    'status': 'True',
                    'lastTransitionTime': kopf.datetime.datetime.now().isoformat(),
                    'reason': 'JobCreated',
                    'message': 'Job was created successfully'
                }]
            }
        }

    except Exception as e:
        logger.error(f"Failed to create job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.delete('mljobs')
def delete_ml_job(spec, name, namespace, logger, **kwargs):
    """处理机器学习任务的删除"""
    try:
        training_spec = spec.get('training')
        if training_spec:
            # 删除training-operator任务
            delete_training_job(name, namespace, training_spec, logger)

        logger.info(f"Successfully deleted ML job: {name}")
        return {
            'status': {
                'phase': 'Deleted',
                'conditions': [{
                    'type': 'Deleted',
                    'status': 'True',
                    'lastTransitionTime': kopf.datetime.datetime.now().isoformat(),
                    'reason': 'JobDeleted',
                    'message': 'Job was deleted successfully'
                }]
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to delete job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.update('mljobs')
def update_ml_job(spec, old, new, name, namespace, logger, **kwargs):
    """处理机器学习任务的更新"""
    try:
        training_spec = spec.get('training')
        if training_spec:
            # 删除旧的training-operator任务
            old_training = old['spec'].get('training')
            if old_training:
                delete_training_job(name, namespace, old_training, logger)
            
            # 创建新的training-operator任务
            create_training_job(name, namespace, training_spec, logger)

        logger.info(f"Successfully updated ML job: {name}")
        return {
            'status': {
                'phase': 'Running',
                'conditions': [{
                    'type': 'Updated',
                    'status': 'True',
                    'lastTransitionTime': kopf.datetime.datetime.now().isoformat(),
                    'reason': 'JobUpdated',
                    'message': 'Job was updated successfully'
                }]
            }
        }
    
    except Exception as e:
        logger.error(f"Failed to update job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.field('mljobs', field='status.phase')
def monitor_job_status(status, name, namespace, logger, **kwargs):
    """监控任务状态变化"""
    try:
        phase = status.get('phase', '').lower()
        current_time = kopf.datetime.datetime.now().isoformat()
        
        if phase == 'succeeded':
            return {
                'status': {
                    'phase': 'Succeeded',
                    'conditions': [{
                        'type': 'Succeeded',
                        'status': 'True',
                        'lastTransitionTime': current_time,
                        'reason': 'JobSucceeded',
                        'message': 'Job completed successfully'
                    }]
                }
            }
        elif phase == 'failed':
            return {
                'status': {
                    'phase': 'Failed',
                    'conditions': [{
                        'type': 'Failed',
                        'status': 'True',
                        'lastTransitionTime': current_time,
                        'reason': 'JobFailed',
                        'message': 'Job failed to complete'
                    }]
                }
            }
        elif phase in ['running', 'active']:
            return {
                'status': {
                    'phase': 'Running',
                    'conditions': [{
                        'type': 'Running',
                        'status': 'True',
                        'lastTransitionTime': current_time,
                        'reason': 'JobRunning',
                        'message': 'Job is running'
                    }]
                }
            }
                
    except Exception as e:
        logger.error(f"Error monitoring job status: {e}") 