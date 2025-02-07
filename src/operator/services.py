"""MLJob业务逻辑服务

处理MLJob资源的核心业务逻辑:
1. 规格验证 - 验证MLJob的配置是否符合要求
2. 资源管理 - 创建、更新、删除training-operator的Job资源
3. 状态管理 - 跟踪和更新Job的运行状态
"""

import logging
from datetime import datetime
from typing import Dict, Any
from kubernetes.client.rest import ApiException
import kopf

from .config import settings
from .utils import (
    create_training_job, delete_training_job, get_training_job_status,
    validate_resource_requests, check_project_quota
)

logger = logging.getLogger(__name__)

def validate_mljob_spec(spec: Dict[str, Any]) -> bool:
    """验证MLJob规格是否合法
    
    Args:
        spec: MLJob的规格配置
        
    Returns:
        bool: 规格是否合法
        
    验证内容:
    1. 必需字段: job_id, project, owner, training
    2. Training配置: api_version, kind, spec
    3. 资源请求配置
    """
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
            if not validate_resource_requests(training["spec"]):
                return False

        return True
    except Exception:
        return False

def validate_project_quota(namespace: str, spec: Dict[str, Any]) -> bool:
    """验证项目资源配额是否满足要求
    
    Args:
        namespace: 项目所在的命名空间
        spec: MLJob的规格配置
        
    Returns:
        bool: 是否满足配额要求
    """
    return check_project_quota(namespace, spec)

def create_training_job_resource(name: str, namespace: str, spec: Dict[str, Any]):
    """创建training-operator Job资源
    
    Args:
        name: Job名称
        namespace: 命名空间
        spec: MLJob规格配置
        
    Raises:
        kopf.TemporaryError: 资源冲突,需要重试
        kopf.PermanentError: 创建失败
    """
    try:
        return create_training_job(name, namespace, spec)
    except ApiException as e:
        if e.status == 409:  # Conflict
            raise kopf.TemporaryError("Resource conflict, retrying...", delay=10)
        raise kopf.PermanentError(f"Failed to create training job: {e}")
    except Exception as e:
        raise kopf.PermanentError(f"Failed to create training job: {e}")

def update_training_job_resource(name: str, namespace: str, old_spec: Dict[str, Any], new_spec: Dict[str, Any]):
    """更新training-operator Job资源
    
    通过删除旧资源并创建新资源的方式实现更新
    
    Args:
        name: Job名称
        namespace: 命名空间
        old_spec: 原MLJob规格
        new_spec: 新MLJob规格
        
    Raises:
        kopf.TemporaryError: 资源冲突,需要重试
        kopf.PermanentError: 更新失败
    """
    try:
        delete_training_job(name, namespace, old_spec)
        return create_training_job(name, namespace, new_spec)
    except ApiException as e:
        if e.status == 409:  # Conflict
            raise kopf.TemporaryError("Resource conflict, retrying...", delay=10)
        raise kopf.PermanentError(f"Failed to update training job: {e}")
    except Exception as e:
        raise kopf.PermanentError(f"Failed to update training job: {e}")

def delete_training_job_resource(name: str, namespace: str, spec: Dict[str, Any]):
    """删除training-operator Job资源
    
    Args:
        name: Job名称
        namespace: 命名空间
        spec: MLJob规格配置
        
    Raises:
        kopf.PermanentError: 删除失败
    """
    try:
        delete_training_job(name, namespace, spec)
    except ApiException as e:
        if e.status == 404:  # Not found
            logger.info(f"Training job for {namespace}/{name} already deleted")
        else:
            raise kopf.PermanentError(f"Failed to delete training job: {e}")
    except Exception as e:
        raise kopf.PermanentError(f"Failed to delete training job: {e}")

def get_training_job_status(name: str, namespace: str, spec: Dict[str, Any]):
    """获取training-operator Job的运行状态
    
    Args:
        name: Job名称
        namespace: 命名空间
        spec: MLJob规格配置
        
    Returns:
        Dict: Job状态信息,包含phase、message等
        
    Raises:
        kopf.TemporaryError: 获取状态失败,需要重试
    """
    try:
        return get_training_job_status(name, namespace, spec)
    except ApiException as e:
        if e.status == 404:  # Not found
            logger.warning(f"Training job for {namespace}/{name} not found")
            return {
                "phase": settings.JOB_PHASES["FAILED"],
                "message": "Training job not found",
                "reason": "NotFound"
            }
        raise kopf.TemporaryError(f"Failed to get training job status: {e}", delay=30)
    except Exception as e:
        raise kopf.TemporaryError(f"Failed to get training job status: {e}", delay=30)

def should_update_training_job(old_spec: Dict[str, Any], new_spec: Dict[str, Any]) -> bool:
    """检查是否需要更新training-operator Job
    
    比较新旧规格中的关键字段是否发生变化
    
    Args:
        old_spec: 原MLJob规格
        new_spec: 新MLJob规格
        
    Returns:
        bool: 是否需要更新
    """
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

def create_mljob_status(phase: str, message: str, **kwargs) -> Dict[str, Any]:
    """创建MLJob状态信息
    
    Args:
        phase: 当前阶段
        message: 状态信息
        **kwargs: 可选参数
            - generation: 资源版本号
            - start_time: 是否添加开始时间
            - completion_time: 是否添加完成时间
            - training_status: training-operator Job的状态信息
            
    Returns:
        Dict: 完整的状态信息
    """
    status = {
        "phase": phase,
        "message": message,
        "observed_generation": kwargs.get("generation", 1)
    }
    
    if kwargs.get("start_time"):
        status["start_time"] = datetime.utcnow().isoformat() + "Z"
    if kwargs.get("completion_time"):
        status["completion_time"] = datetime.utcnow().isoformat() + "Z"
        
    if "training_status" in kwargs:
        status["training_status"] = kwargs["training_status"]
        
    return status 