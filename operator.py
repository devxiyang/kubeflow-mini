import kopf
import kubernetes.client as k8s
from kubernetes.client.rest import ApiException
import yaml
import logging

# 配置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建Kubernetes API客户端
api = k8s.CustomObjectsApi()

@kopf.on.create('mljobs')
def create_ml_job(spec, name, namespace, logger, **kwargs):
    """
    处理新的机器学习任务创建
    """
    try:
        # 从spec中获取任务类型和配置
        job_type = spec.get('type', 'pytorch').lower()
        framework_version = spec.get('frameworkVersion', '1.13.1')
        worker_replicas = spec.get('workerReplicas', 1)
        image = spec.get('image')
        command = spec.get('command', [])
        
        if not image:
            raise kopf.PermanentError("Image must be specified in the job spec")

        # 创建训练任务配置
        if job_type == 'pytorch':
            job_manifest = create_pytorch_job_manifest(
                name=name,
                namespace=namespace,
                image=image,
                command=command,
                worker_replicas=worker_replicas,
                framework_version=framework_version
            )
        else:
            raise kopf.PermanentError(f"Unsupported job type: {job_type}")

        # 创建训练任务
        api.create_namespaced_custom_object(
            group="kubeflow.org",
            version="v1",
            namespace=namespace,
            plural="pytorchjobs",
            body=job_manifest,
        )
        
        logger.info(f"Successfully created {job_type} training job: {name}")
        return {"status": "created"}

    except ApiException as e:
        raise kopf.PermanentError(f"Failed to create training job: {e}")

def create_pytorch_job_manifest(name, namespace, image, command, worker_replicas, framework_version):
    """
    创建PyTorch训练任务的配置清单
    """
    return {
        "apiVersion": "kubeflow.org/v1",
        "kind": "PyTorchJob",
        "metadata": {
            "name": name,
            "namespace": namespace
        },
        "spec": {
            "pytorchReplicaSpecs": {
                "Worker": {
                    "replicas": worker_replicas,
                    "restartPolicy": "OnFailure",
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "pytorch",
                                    "image": image,
                                    "command": command
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

@kopf.on.delete('mljobs')
def delete_ml_job(spec, name, namespace, logger, **kwargs):
    """
    处理机器学习任务的删除
    """
    try:
        job_type = spec.get('type', 'pytorch').lower()
        
        if job_type == 'pytorch':
            api.delete_namespaced_custom_object(
                group="kubeflow.org",
                version="v1",
                namespace=namespace,
                plural="pytorchjobs",
                name=name,
            )
        
        logger.info(f"Successfully deleted {job_type} training job: {name}")
        return {"status": "deleted"}
        
    except ApiException as e:
        if e.status == 404:
            logger.warning(f"Training job {name} not found, might have been already deleted")
            return {"status": "not found"}
        raise kopf.PermanentError(f"Failed to delete training job: {e}")

@kopf.on.update('mljobs')
def update_ml_job(spec, old, new, name, namespace, logger, **kwargs):
    """
    处理机器学习任务的更新
    """
    try:
        # 删除旧的任务
        delete_ml_job(old, name, namespace, logger)
        # 创建新的任务
        return create_ml_job(spec, name, namespace, logger)
    
    except Exception as e:
        raise kopf.PermanentError(f"Failed to update training job: {e}") 