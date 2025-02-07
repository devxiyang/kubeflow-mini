"""Operator处理函数"""
import kopf
import logging
import kubernetes.client as k8s
from kubernetes.client.rest import ApiException
from datetime import datetime

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

def create_training_job(name, namespace, training_spec, spec, logger):
    """创建training-operator任务"""
    try:
        # 从training_spec中获取API信息
        group, version = training_spec['apiVersion'].split('/')
        kind = training_spec['kind'].lower() + 's'  # 转换为复数形式作为plural

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
    
    except Exception as e:
        logger.error(f"Failed to update job: {e}")
        raise kopf.PermanentError(str(e))

@kopf.on.field('mljobs', field='status.phase')
def monitor_job_status(status, body, name, namespace, logger, **kwargs):
    """监控任务状态变化"""
    try:
        phase = status.get('phase', '').lower()
        current_time = datetime.utcnow().isoformat() + "Z"
        
        # 获取开始时间
        start_time = body.get('status', {}).get('startTime')
        
        # 计算持续时间
        if start_time:
            start = datetime.fromisoformat(start_time.rstrip('Z'))
            current = datetime.utcnow()
            duration = str(current - start)
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