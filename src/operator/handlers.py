"""Operator事件处理器"""

import logging
import kopf
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from datetime import datetime
from typing import Dict, Any, Optional

from .config import settings
from .models import MLJob, MLJobStatus
from .utils import create_training_job, delete_training_job, get_training_job_status

# 配置日志
logger = logging.getLogger(__name__)

# Finalizer名称
FINALIZER = f"{settings.GROUP}/cleanup"

# ===================== MLJob 处理器 =====================

@kopf.on.create(settings.GROUP, settings.VERSION, settings.PLURAL)
def create_mljob(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **kwargs):
    """处理MLJob创建事件"""
    try:
        # 获取资源信息
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Creating MLJob {namespace}/{name}")

        # 验证规格
        if not _validate_mljob_spec(spec):
            raise kopf.PermanentError("Invalid MLJob specification")

        # 检查项目配额
        if not _check_project_quota(namespace, spec):
            raise kopf.PermanentError("Project quota exceeded")

        # 创建对应的Training Job
        try:
            job = create_training_job(name, namespace, spec)
        except ApiException as e:
            if e.status == 409:  # Conflict
                raise kopf.TemporaryError("Resource conflict, retrying...", delay=10)
            raise kopf.PermanentError(f"Failed to create training job: {e}")
        except Exception as e:
            raise kopf.PermanentError(f"Failed to create training job: {e}")

        # 返回状态
        return {
            "phase": settings.JOB_PHASES["CREATED"],
            "message": "Created training job successfully",
            "start_time": datetime.utcnow().isoformat() + "Z",
            "observed_generation": meta.get("generation", 1)
        }

    except kopf.PermanentError as e:
        logger.error(f"Permanent error creating MLJob {namespace}/{name}: {str(e)}")
        return {
            "phase": settings.JOB_PHASES["FAILED"],
            "message": str(e),
            "reason": "CreateError",
            "observed_generation": meta.get("generation", 1)
        }
    except kopf.TemporaryError as e:
        logger.warning(f"Temporary error creating MLJob {namespace}/{name}: {str(e)}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error creating MLJob {namespace}/{name}")
        return {
            "phase": settings.JOB_PHASES["FAILED"],
            "message": f"Unexpected error: {str(e)}",
            "reason": "InternalError",
            "observed_generation": meta.get("generation", 1)
        }

@kopf.on.update(settings.GROUP, settings.VERSION, settings.PLURAL)
def update_mljob(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], 
                 old: Dict[str, Any], new: Dict[str, Any], diff, **kwargs):
    """处理MLJob更新事件"""
    try:
        # 获取资源信息
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Updating MLJob {namespace}/{name}")

        # 验证新规格
        if not _validate_mljob_spec(new["spec"]):
            raise kopf.PermanentError("Invalid MLJob specification")

        # 检查项目配额
        if not _check_project_quota(namespace, new["spec"]):
            raise kopf.PermanentError("Project quota exceeded")

        # 检查是否需要更新Training Job
        if _should_update_training_job(old["spec"], new["spec"]):
            try:
                # 删除旧的Training Job
                delete_training_job(name, namespace, old["spec"])
                # 创建新的Training Job
                job = create_training_job(name, namespace, new["spec"])
            except ApiException as e:
                if e.status == 409:  # Conflict
                    raise kopf.TemporaryError("Resource conflict, retrying...", delay=10)
                raise kopf.PermanentError(f"Failed to update training job: {e}")
            except Exception as e:
                raise kopf.PermanentError(f"Failed to update training job: {e}")

            return {
                "phase": settings.JOB_PHASES["CREATED"],
                "message": "Recreated training job successfully",
                "start_time": datetime.utcnow().isoformat() + "Z",
                "observed_generation": meta.get("generation", 1)
            }

    except kopf.PermanentError as e:
        logger.error(f"Permanent error updating MLJob {namespace}/{name}: {str(e)}")
        return {
            "phase": settings.JOB_PHASES["FAILED"],
            "message": str(e),
            "reason": "UpdateError",
            "observed_generation": meta.get("generation", 1)
        }
    except kopf.TemporaryError as e:
        logger.warning(f"Temporary error updating MLJob {namespace}/{name}: {str(e)}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating MLJob {namespace}/{name}")
        return {
            "phase": settings.JOB_PHASES["FAILED"],
            "message": f"Unexpected error: {str(e)}",
            "reason": "InternalError",
            "observed_generation": meta.get("generation", 1)
        }

@kopf.on.delete(settings.GROUP, settings.VERSION, settings.PLURAL)
def delete_mljob(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **kwargs):
    """处理MLJob删除事件"""
    try:
        # 获取资源信息
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Deleting MLJob {namespace}/{name}")

        try:
            # 删除Training Job
            delete_training_job(name, namespace, spec)
        except ApiException as e:
            if e.status == 404:  # Not found
                logger.info(f"Training job for {namespace}/{name} already deleted")
            else:
                raise kopf.PermanentError(f"Failed to delete training job: {e}")
        except Exception as e:
            raise kopf.PermanentError(f"Failed to delete training job: {e}")

        return {
            "phase": settings.JOB_PHASES["DELETED"],
            "message": "Deleted training job successfully",
            "completion_time": datetime.utcnow().isoformat() + "Z"
        }

    except kopf.PermanentError as e:
        logger.error(f"Permanent error deleting MLJob {namespace}/{name}: {str(e)}")
        return {
            "phase": settings.JOB_PHASES["FAILED"],
            "message": str(e),
            "reason": "DeleteError"
        }
    except Exception as e:
        logger.exception(f"Unexpected error deleting MLJob {namespace}/{name}")
        return {
            "phase": settings.JOB_PHASES["FAILED"],
            "message": f"Unexpected error: {str(e)}",
            "reason": "InternalError"
        }

@kopf.timer(settings.GROUP, settings.VERSION, settings.PLURAL, interval=30.0)
def reconcile_mljob(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **kwargs):
    """定期调谐MLJob状态"""
    try:
        # 获取资源信息
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.debug(f"Reconciling MLJob {namespace}/{name}")

        # 检查Training Job状态
        try:
            training_status = get_training_job_status(name, namespace, spec)
        except ApiException as e:
            if e.status == 404:  # Not found
                # Training Job不存在,可能需要重建
                logger.warning(f"Training job for {namespace}/{name} not found")
                return {
                    "phase": settings.JOB_PHASES["FAILED"],
                    "message": "Training job not found",
                    "reason": "NotFound"
                }
            raise kopf.TemporaryError(f"Failed to get training job status: {e}", delay=30)
        except Exception as e:
            raise kopf.TemporaryError(f"Failed to get training job status: {e}", delay=30)

        if not training_status:
            return

        # 更新状态
        phase = training_status.get("phase", settings.JOB_PHASES["RUNNING"])
        return {
            "phase": phase,
            "message": f"Training job is {phase.lower()}",
            "training_status": training_status,
            "completion_time": (
                datetime.utcnow().isoformat() + "Z"
                if phase in [settings.JOB_PHASES["SUCCEEDED"], settings.JOB_PHASES["FAILED"]]
                else None
            ),
            "observed_generation": meta.get("generation", 1)
        }

    except kopf.TemporaryError as e:
        logger.warning(f"Temporary error reconciling MLJob {namespace}/{name}: {str(e)}")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error reconciling MLJob {namespace}/{name}")
        # 不更新状态,等待下次重试

# ===================== Project 处理器 =====================

@kopf.on.create(settings.GROUP, settings.VERSION, "projects")
def create_project(spec, meta, status, **kwargs):
    """处理Project创建事件"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Creating Project {namespace}/{name}")
        
        # 验证配额设置
        if not _validate_project_quotas(spec):
            raise ValueError("Invalid project quotas")
            
        return {
            "phase": "Active",
            "message": "Project is active",
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to create Project {namespace}/{name}: {str(e)}")
        return {
            "phase": "Failed",
            "message": str(e),
            "reason": "CreateError"
        }

@kopf.on.update(settings.GROUP, settings.VERSION, "projects")
def update_project(spec, meta, status, old, new, diff, **kwargs):
    """处理Project更新事件"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Updating Project {namespace}/{name}")
        
        # 验证新的配额设置
        if not _validate_project_quotas(new["spec"]):
            raise ValueError("Invalid project quotas")
            
        # 检查是否需要更新关联的MLJobs
        if _should_update_jobs(old["spec"], new["spec"]):
            _update_project_jobs(name, namespace, new["spec"])
            
        return {
            "phase": "Active",
            "message": "Project updated",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to update Project {namespace}/{name}: {str(e)}")
        return {
            "phase": "Failed",
            "message": str(e),
            "reason": "UpdateError"
        }

@kopf.on.delete(settings.GROUP, settings.VERSION, "projects")
def delete_project(spec, meta, status, **kwargs):
    """处理Project删除事件"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Deleting Project {namespace}/{name}")
        
        # 删除关联的MLJobs
        _delete_project_jobs(name, namespace)
        
        return {
            "phase": "Deleted",
            "message": "Project and associated jobs deleted",
            "deleted_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to delete Project {namespace}/{name}: {str(e)}")
        return {
            "phase": "Failed",
            "message": str(e),
            "reason": "DeleteError"
        }

# ===================== Owner 处理器 =====================

@kopf.on.create(settings.GROUP, settings.VERSION, "owners")
def create_owner(spec, meta, status, **kwargs):
    """处理Owner创建事件"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Creating Owner {namespace}/{name}")
        
        # 验证Owner配置
        if not _validate_owner_config(spec):
            raise ValueError("Invalid owner configuration")
            
        return {
            "phase": "Active",
            "message": "Owner is active",
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to create Owner {namespace}/{name}: {str(e)}")
        return {
            "phase": "Failed",
            "message": str(e),
            "reason": "CreateError"
        }

@kopf.on.update(settings.GROUP, settings.VERSION, "owners")
def update_owner(spec, meta, status, old, new, diff, **kwargs):
    """处理Owner更新事件"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Updating Owner {namespace}/{name}")
        
        # 验证新的Owner配置
        if not _validate_owner_config(new["spec"]):
            raise ValueError("Invalid owner configuration")
            
        # 检查是否需要更新关联的Projects和MLJobs
        if _should_update_owner_resources(old["spec"], new["spec"]):
            _update_owner_resources(name, namespace, new["spec"])
            
        return {
            "phase": "Active",
            "message": "Owner updated",
            "updated_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to update Owner {namespace}/{name}: {str(e)}")
        return {
            "phase": "Failed",
            "message": str(e),
            "reason": "UpdateError"
        }

@kopf.on.delete(settings.GROUP, settings.VERSION, "owners")
def delete_owner(spec, meta, status, **kwargs):
    """处理Owner删除事件"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Deleting Owner {namespace}/{name}")
        
        # 删除关联的Projects和MLJobs
        _delete_owner_resources(name, namespace)
        
        return {
            "phase": "Deleted",
            "message": "Owner and associated resources deleted",
            "deleted_at": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"Failed to delete Owner {namespace}/{name}: {str(e)}")
        return {
            "phase": "Failed",
            "message": str(e),
            "reason": "DeleteError"
        }

# ===================== 辅助函数 =====================

def _validate_project_quotas(spec):
    """验证项目配额设置"""
    try:
        quotas = spec.get("quotas", {})
        return (
            isinstance(quotas.get("gpu_limit"), int) and
            isinstance(quotas.get("cpu_limit"), (int, float)) and
            isinstance(quotas.get("memory_limit"), str) and
            isinstance(quotas.get("max_jobs"), int)
        )
    except Exception:
        return False

def _validate_owner_config(spec):
    """验证Owner配置"""
    try:
        return (
            isinstance(spec.get("name"), str) and
            isinstance(spec.get("email"), str) and
            isinstance(spec.get("role"), str)
        )
    except Exception:
        return False

def _should_update_jobs(old_spec, new_spec):
    """检查是否需要更新MLJobs"""
    old_quotas = old_spec.get("quotas", {})
    new_quotas = new_spec.get("quotas", {})
    return old_quotas != new_quotas

def _should_update_owner_resources(old_spec, new_spec):
    """检查是否需要更新Owner关联资源"""
    return (
        old_spec.get("role") != new_spec.get("role") or
        old_spec.get("permissions") != new_spec.get("permissions")
    )

def _update_project_jobs(project_name, namespace, spec):
    """更新项目关联的MLJobs"""
    try:
        api = client.CustomObjectsApi()
        jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"project={project_name}"
        )
        
        for job in jobs.get("items", []):
            # 根据新的项目配额更新Job
            _update_job_resources(job, spec.get("quotas", {}))
    except Exception as e:
        logger.error(f"Failed to update project jobs: {str(e)}")
        raise

def _update_owner_resources(owner_name, namespace, spec):
    """更新Owner关联的资源"""
    try:
        api = client.CustomObjectsApi()
        
        # 更新Projects
        projects = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural="projects",
            label_selector=f"owner={owner_name}"
        )
        
        for project in projects.get("items", []):
            # 根据新的Owner配置更新Project
            _update_project_permissions(project, spec)
            
        # 更新MLJobs
        jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"owner={owner_name}"
        )
        
        for job in jobs.get("items", []):
            # 根据新的Owner配置更新Job
            _update_job_permissions(job, spec)
    except Exception as e:
        logger.error(f"Failed to update owner resources: {str(e)}")
        raise

def _delete_project_jobs(project_name, namespace):
    """删除项目关联的MLJobs"""
    try:
        api = client.CustomObjectsApi()
        jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"project={project_name}"
        )
        
        for job in jobs.get("items", []):
            name = job["metadata"]["name"]
            api.delete_namespaced_custom_object(
                group=settings.GROUP,
                version=settings.VERSION,
                namespace=namespace,
                plural=settings.PLURAL,
                name=name
            )
    except Exception as e:
        logger.error(f"Failed to delete project jobs: {str(e)}")
        raise

def _delete_owner_resources(owner_name, namespace):
    """删除Owner关联的资源"""
    try:
        api = client.CustomObjectsApi()
        
        # 删除Projects
        projects = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural="projects",
            label_selector=f"owner={owner_name}"
        )
        
        for project in projects.get("items", []):
            name = project["metadata"]["name"]
            api.delete_namespaced_custom_object(
                group=settings.GROUP,
                version=settings.VERSION,
                namespace=namespace,
                plural="projects",
                name=name
            )
            
        # MLJobs会通过级联删除自动删除
    except Exception as e:
        logger.error(f"Failed to delete owner resources: {str(e)}")
        raise

def _validate_mljob_spec(spec: Dict[str, Any]) -> bool:
    """验证MLJob规格"""
    try:
        # 验证必需字段
        required_fields = ["job_id", "project", "owner", "training"]
        if not all(field in spec for field in required_fields):
            return False

        # 验证training配置
        training = spec.get("training", {})
        if not all(field in training for field in ["api_version", "kind", "spec"]):
            return False

        # 验证资源请求
        if "spec" in training:
            if not _validate_resource_requests(training["spec"]):
                return False

        return True
    except Exception:
        return False

def _validate_resource_requests(spec: Dict[str, Any]) -> bool:
    """验证资源请求"""
    try:
        # 验证CPU和内存请求
        for replica_spec in spec.values():
            if isinstance(replica_spec, dict):
                template = replica_spec.get("template", {})
                containers = template.get("spec", {}).get("containers", [])
                for container in containers:
                    resources = container.get("resources", {})
                    requests = resources.get("requests", {})
                    if not all(k in requests for k in ["cpu", "memory"]):
                        return False
        return True
    except Exception:
        return False

def _check_project_quota(namespace: str, spec: Dict[str, Any]) -> bool:
    """检查项目配额"""
    try:
        project_name = spec.get("project")
        if not project_name:
            return False

        # 获取项目配额
        api = client.CustomObjectsApi()
        project = api.get_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural="projects",
            name=project_name
        )

        quotas = project.get("spec", {}).get("quotas", {})
        if not quotas:
            return False

        # 获取项目当前使用量
        current_jobs = api.list_namespaced_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            namespace=namespace,
            plural=settings.PLURAL,
            label_selector=f"project={project_name}"
        )

        # 检查配额
        job_count = len(current_jobs.get("items", []))
        if job_count >= quotas.get("max_jobs", 0):
            return False

        return True
    except ApiException as e:
        if e.status == 404:  # Project not found
            return False
        raise
    except Exception:
        return False

def _should_update_training_job(old_spec: Dict[str, Any], new_spec: Dict[str, Any]) -> bool:
    """检查是否需要更新Training Job"""
    try:
        old_training = old_spec.get("training", {})
        new_training = new_spec.get("training", {})
        
        # 检查关键字段
        fields_to_check = ["api_version", "kind", "spec"]
        for field in fields_to_check:
            if old_training.get(field) != new_training.get(field):
                return True
                
        return False
    except Exception:
        # 如果出现异常,为安全起见返回True
        return True 