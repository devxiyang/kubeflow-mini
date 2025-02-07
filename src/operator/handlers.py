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
from datetime import datetime

from .config import settings
from . import services

logger = logging.getLogger(__name__)

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

@kopf.timer(settings.GROUP, settings.VERSION, settings.PLURAL, interval=30.0)
def reconcile_mljob(spec: Dict[str, Any], meta: Dict[str, Any], **kwargs):
    """定期调谐MLJob状态
    
    Args:
        spec: MLJob规格配置
        meta: MLJob元数据
        **kwargs: kopf框架传入的其他参数
    """
    try:
        name = meta.get("name")
        namespace = meta.get("namespace", "default")
        logger.debug(f"Reconciling MLJob {namespace}/{name}")

        # 获取Training Job状态
        training_status = services.get_training_job_status(name, namespace, spec)
        if not training_status:
            return

        # 更新状态
        phase = training_status.get("phase", settings.JOB_PHASES["RUNNING"])
        status = services.create_mljob_status(
            phase,
            f"Training job is {phase.lower()}",
            generation=meta.get("generation", 1),
            training_status=training_status
        )
        
        # 如果完成则添加完成时间
        if phase in [settings.JOB_PHASES["SUCCEEDED"], settings.JOB_PHASES["FAILED"]]:
            status["completion_time"] = datetime.utcnow().isoformat() + "Z"
            
        return status

    except kopf.TemporaryError:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error reconciling MLJob {namespace}/{name}")
        # 不更新状态,等待下次重试 