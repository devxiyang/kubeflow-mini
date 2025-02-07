"""MLJob事件处理器

处理MLJob资源的事件:
1. 创建事件 - 处理MLJob资源的创建
2. 更新事件 - 处理MLJob资源的更新
3. 删除事件 - 处理MLJob资源的删除
4. 状态同步 - 定期同步MLJob与Training Job的状态
"""

import logging
import kopf
from typing import Dict, Any
from datetime import datetime, timedelta

from .config import settings
from . import services
from . import utils

logger = logging.getLogger(__name__)

@kopf.on.startup()
def configure(settings: kopf.OperatorSettings, **_):
    """配置operator"""
    # 配置重试
    settings.posting.enabled = True
    settings.posting.level = logging.INFO
    
    # 配置调谐间隔
    settings.scanning.period = settings.RECONCILE.interval

@kopf.on.create(settings.GROUP, settings.VERSION, settings.PLURAL)
def create_mljob(spec: Dict[str, Any], meta: Dict[str, Any], **kwargs):
    """处理MLJob创建事件
    
    Args:
        spec: MLJob规格配置
        meta: MLJob元数据
        **kwargs: kopf框架传入的其他参数
    """
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Creating MLJob {namespace}/{name}")

        # 验证和检查
        if not services.validate_mljob_spec(spec):
            raise kopf.PermanentError("Invalid MLJob specification")
        if not services.validate_project_quota(namespace, spec):
            raise kopf.PermanentError("Project quota exceeded")
            
        # 创建Training Job
        services.create_training_job_resource(name, namespace, spec)
        
        # 返回状态
        return services.create_mljob_status(
            settings.JOB_PHASES["CREATED"],
            "Created training job successfully",
            generation=meta.get("generation", 1),
            start_time=True
        )

    except kopf.PermanentError as e:
        logger.error(f"Permanent error creating MLJob {namespace}/{name}: {str(e)}")
        return services.create_mljob_status(
            settings.JOB_PHASES["FAILED"],
            str(e),
            generation=meta.get("generation", 1),
            reason="CreateError"
        )
    except kopf.TemporaryError:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error creating MLJob {namespace}/{name}")
        return services.create_mljob_status(
            settings.JOB_PHASES["FAILED"],
            f"Unexpected error: {str(e)}",
            generation=meta.get("generation", 1),
            reason="InternalError"
        )

@kopf.on.update(settings.GROUP, settings.VERSION, settings.PLURAL)
def update_mljob(spec: Dict[str, Any], meta: Dict[str, Any],
                old: Dict[str, Any], new: Dict[str, Any], **kwargs):
    """处理MLJob更新事件
    
    Args:
        spec: 当前MLJob规格配置
        meta: MLJob元数据
        old: 原MLJob完整配置
        new: 新MLJob完整配置
        **kwargs: kopf框架传入的其他参数
    """
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Updating MLJob {namespace}/{name}")

        # 验证和检查
        if not services.validate_mljob_spec(new["spec"]):
            raise kopf.PermanentError("Invalid MLJob specification")
        if not services.validate_project_quota(namespace, new["spec"]):
            raise kopf.PermanentError("Project quota exceeded")
            
        # 更新Training Job
        if services.should_update_training_job(old["spec"], new["spec"]):
            services.update_training_job_resource(name, namespace, old["spec"], new["spec"])
            
        return services.create_mljob_status(
            settings.JOB_PHASES["CREATED"],
            "Updated training job successfully",
            generation=meta.get("generation", 1),
            start_time=True
        )

    except kopf.PermanentError as e:
        logger.error(f"Permanent error updating MLJob {namespace}/{name}: {str(e)}")
        return services.create_mljob_status(
            settings.JOB_PHASES["FAILED"],
            str(e),
            generation=meta.get("generation", 1),
            reason="UpdateError"
        )
    except kopf.TemporaryError:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating MLJob {namespace}/{name}")
        return services.create_mljob_status(
            settings.JOB_PHASES["FAILED"],
            f"Unexpected error: {str(e)}",
            generation=meta.get("generation", 1),
            reason="InternalError"
        )

@kopf.on.delete(settings.GROUP, settings.VERSION, settings.PLURAL)
def delete_mljob(spec: Dict[str, Any], meta: Dict[str, Any], **kwargs):
    """处理MLJob删除事件
    
    Args:
        spec: MLJob规格配置
        meta: MLJob元数据
        **kwargs: kopf框架传入的其他参数
    """
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Deleting MLJob {namespace}/{name}")

        # 删除Training Job
        services.delete_training_job_resource(name, namespace, spec)
        
        return services.create_mljob_status(
            settings.JOB_PHASES["DELETED"],
            "Deleted training job successfully",
            completion_time=True
        )

    except kopf.PermanentError as e:
        logger.error(f"Permanent error deleting MLJob {namespace}/{name}: {str(e)}")
        return services.create_mljob_status(
            settings.JOB_PHASES["FAILED"],
            str(e),
            reason="DeleteError"
        )
    except Exception as e:
        logger.exception(f"Unexpected error deleting MLJob {namespace}/{name}")
        return services.create_mljob_status(
            settings.JOB_PHASES["FAILED"],
            f"Unexpected error: {str(e)}",
            reason="InternalError"
        )

@kopf.timer(settings.GROUP, settings.VERSION, settings.PLURAL, 
           interval=settings.RECONCILE.interval)
def reconcile_mljob(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **kwargs):
    """定期调谐MLJob状态
    
    Args:
        spec: MLJob规格配置
        meta: MLJob元数据
        status: 当前MLJob状态
        **kwargs: kopf框架传入的其他参数
    """
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.debug(f"Reconciling MLJob {namespace}/{name}")

        # 检查资源年龄
        creation_time = meta.get("creationTimestamp")
        if creation_time:
            age = datetime.utcnow() - datetime.fromisoformat(creation_time.rstrip("Z"))
            if age.days > settings.RESOURCE.max_age:
                logger.info(f"MLJob {namespace}/{name} exceeded max age, cleaning up")
                services.delete_training_job_resource(name, namespace, spec)
                return services.create_mljob_status(
                    settings.JOB_PHASES["DELETED"],
                    "Resource exceeded max age",
                    completion_time=True
                )

        # 获取Training Job状态
        training_status = services.get_training_job_status(name, namespace, spec)
        if not training_status:
            # 检查错误次数
            error_count = status.get("reconcile_errors", 0)
            if error_count >= settings.RECONCILE.error_threshold:
                return services.create_mljob_status(
                    settings.JOB_PHASES["ERROR"],
                    "Failed to get training job status after multiple attempts",
                    reason="ReconcileError",
                    reconcile_errors=error_count + 1
                )
            return services.create_mljob_status(
                settings.JOB_PHASES["UNKNOWN"],
                "Training job status not available",
                reconcile_errors=error_count + 1
            )

        # 更新状态
        phase = training_status.get("phase", settings.JOB_PHASES["RUNNING"])
        status = services.create_mljob_status(
            phase,
            f"Training job is {phase.lower()}",
            generation=meta.get("generation", 1),
            training_status=training_status,
            reconcile_errors=0  # 重置错误计数
        )
        
        # 如果完成则添加完成时间
        if phase in [settings.JOB_PHASES["SUCCEEDED"], settings.JOB_PHASES["FAILED"]]:
            status["completion_time"] = datetime.utcnow().isoformat() + "Z"
            
        return status

    except kopf.TemporaryError:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error reconciling MLJob {namespace}/{name}")
        error_count = status.get("reconcile_errors", 0)
        return services.create_mljob_status(
            settings.JOB_PHASES["ERROR"],
            f"Reconciliation failed: {str(e)}",
            reason="ReconcileError",
            reconcile_errors=error_count + 1
        )

@kopf.timer(settings.GROUP, settings.VERSION, settings.PLURAL,
           interval=settings.RESOURCE.cleanup_interval)
def cleanup_resources(**kwargs):
    """定期清理资源"""
    try:
        logger.info("Starting resource cleanup")
        
        # 获取所有MLJob
        api = utils.get_k8s_api()
        jobs = api.list_cluster_custom_object(
            group=settings.GROUP,
            version=settings.VERSION,
            plural=settings.PLURAL
        )
        
        for job in jobs.get("items", []):
            try:
                name = job["metadata"]["name"]
                namespace = job["metadata"]["namespace"]
                
                # 检查是否需要清理
                if utils.should_cleanup_resource(job):
                    logger.info(f"Cleaning up MLJob {namespace}/{name}")
                    services.delete_training_job_resource(name, namespace, job["spec"])
                    
            except Exception as e:
                logger.error(f"Failed to cleanup job {name}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Failed to cleanup resources: {str(e)}")

@kopf.on.resume(settings.GROUP, settings.VERSION, settings.PLURAL)
def resume_mljob(spec: Dict[str, Any], meta: Dict[str, Any], status: Dict[str, Any], **kwargs):
    """处理operator重启后的MLJob恢复"""
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.info(f"Resuming MLJob {namespace}/{name}")
        
        # 检查Training Job是否存在
        training_status = services.get_training_job_status(name, namespace, spec)
        if not training_status:
            # Training Job不存在，需要重建
            services.create_training_job_resource(name, namespace, spec)
            return services.create_mljob_status(
                settings.JOB_PHASES["CREATED"],
                "Recreated training job after operator restart",
                generation=meta.get("generation", 1),
                start_time=True
            )
            
        # Training Job存在，返回当前状态
        phase = training_status.get("phase", settings.JOB_PHASES["RUNNING"])
        return services.create_mljob_status(
            phase,
            f"Resumed monitoring of training job",
            generation=meta.get("generation", 1),
            training_status=training_status
        )
        
    except Exception as e:
        logger.exception(f"Failed to resume MLJob {namespace}/{name}")
        return services.create_mljob_status(
            settings.JOB_PHASES["ERROR"],
            f"Failed to resume job: {str(e)}",
            reason="ResumeError"
        ) 