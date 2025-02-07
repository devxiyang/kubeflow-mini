"""MLJob业务逻辑服务

处理MLJob资源的核心业务逻辑:
1. 规格验证 - 验证MLJob的配置是否符合要求
2. 资源管理 - 创建、更新、删除training-operator的Job资源
3. 状态管理 - 跟踪和更新Job的运行状态
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from kubernetes.client.rest import ApiException
import kopf
from kubernetes import client as k8s_client

from .config import settings
from .utils import (
    create_training_job, delete_training_job, get_training_job_status,
    validate_resource_requests, check_project_quota, exponential_backoff,
    get_k8s_api
)
from .models import MLJobStatus, MLJobCondition

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
    except Exception as e:
        logger.error(f"Failed to validate MLJob spec: {str(e)}")
        return False

def validate_project_quota(namespace: str, spec: Dict[str, Any]) -> bool:
    """验证项目资源配额是否满足要求
    
    Args:
        namespace: 项目所在的命名空间
        spec: MLJob的规格配置
        
    Returns:
        bool: 是否满足配额要求
    """
    try:
        # 获取namespace的资源配额
        quota = k8s_client.CoreV1Api().read_namespaced_resource_quota(
            name=f"{namespace}-quota",
            namespace=namespace
        )
        
        if not quota or not quota.status:
            logger.warning(f"No resource quota found for namespace {namespace}")
            return False
            
        # 解析当前使用量和限制
        used = quota.status.used or {}
        hard = quota.status.hard or {}
        
        # 从spec中获取资源请求
        training = spec.get("training", {}).get("spec", {})
        if not training:
            return False
            
        resources = training.get("template", {}).get("spec", {}).get("containers", [{}])[0].get("resources", {})
        requests = resources.get("requests", {})
        
        # 检查CPU
        cpu_request = _parse_cpu(requests.get("cpu", "0"))
        cpu_used = _parse_cpu(used.get("requests.cpu", "0"))
        cpu_limit = _parse_cpu(hard.get("limits.cpu", "0"))
        if cpu_request + cpu_used > cpu_limit:
            logger.warning(f"CPU quota exceeded: {cpu_request + cpu_used} > {cpu_limit}")
            return False
            
        # 检查内存
        memory_request = _parse_memory(requests.get("memory", "0"))
        memory_used = _parse_memory(used.get("requests.memory", "0"))
        memory_limit = _parse_memory(hard.get("limits.memory", "0"))
        if memory_request + memory_used > memory_limit:
            logger.warning(f"Memory quota exceeded: {memory_request + memory_used} > {memory_limit}")
            return False
            
        # 检查GPU
        gpu_request = int(requests.get("nvidia.com/gpu", 0))
        gpu_used = int(used.get("requests.nvidia.com/gpu", 0))
        gpu_limit = int(hard.get("limits.nvidia.com/gpu", 0))
        if gpu_request + gpu_used > gpu_limit:
            logger.warning(f"GPU quota exceeded: {gpu_request + gpu_used} > {gpu_limit}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to validate project quota: {str(e)}")
        return False

def _parse_memory(memory_str: str) -> int:
    """解析内存字符串为字节数"""
    try:
        if isinstance(memory_str, (int, float)):
            return int(memory_str)
            
        if not memory_str:
            return 0
            
        memory_str = str(memory_str).strip().lower()
        
        # 转换为字节
        multipliers = {
            'k': 1024,
            'm': 1024 * 1024,
            'g': 1024 * 1024 * 1024,
            't': 1024 * 1024 * 1024 * 1024,
            'ki': 1024,
            'mi': 1024 * 1024,
            'gi': 1024 * 1024 * 1024,
            'ti': 1024 * 1024 * 1024 * 1024
        }
        
        number = float(''.join([c for c in memory_str if c.isdigit() or c == '.']))
        unit = ''.join([c for c in memory_str if not c.isdigit() and c != '.'])
        
        if not unit:
            return int(number)
            
        if unit not in multipliers:
            return 0
            
        return int(number * multipliers[unit])
    except:
        return 0

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
        # 添加标准标签
        labels = {
            **settings.LABELS,
            "job-id": spec.get("job_id", ""),
            "project": spec.get("project", ""),
            "owner": spec.get("owner", "")
        }
        if spec.get("labels"):
            labels.update(spec["labels"])
            
        return create_training_job(name, namespace, spec, labels)
    except ApiException as e:
        if e.status == 409:  # Conflict
            raise kopf.TemporaryError(
                "Resource conflict, retrying...",
                delay=exponential_backoff(1)
            )
        raise kopf.PermanentError(f"Failed to create training job: {e}")
    except Exception as e:
        raise kopf.PermanentError(f"Failed to create training job: {e}")

def update_training_job_resource(name: str, namespace: str, 
                               old_spec: Dict[str, Any], new_spec: Dict[str, Any]):
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
        # 删除旧资源
        delete_training_job(name, namespace, old_spec)
        
        # 创建新资源
        labels = {
            **settings.LABELS,
            "job-id": new_spec.get("job_id", ""),
            "project": new_spec.get("project", ""),
            "owner": new_spec.get("owner", "")
        }
        if new_spec.get("labels"):
            labels.update(new_spec["labels"])
            
        return create_training_job(name, namespace, new_spec, labels)
    except ApiException as e:
        if e.status == 409:  # Conflict
            raise kopf.TemporaryError(
                "Resource conflict, retrying...",
                delay=exponential_backoff(1)
            )
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

def get_training_job_status(name: str, namespace: str, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
            return None
        raise kopf.TemporaryError(
            f"Failed to get training job status: {e}",
            delay=exponential_backoff(1)
        )
    except Exception as e:
        raise kopf.TemporaryError(
            f"Failed to get training job status: {e}",
            delay=exponential_backoff(1)
        )

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
                
        # 检查标签变化
        if old_spec.get("labels") != new_spec.get("labels"):
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
    try:
        # 创建基本状态
        status = MLJobStatus(
            phase=phase,
            message=message,
            reason=kwargs.get("reason"),
            training_status=kwargs.get("training_status"),
            observed_generation=kwargs.get("generation", 1),
            reconcile_errors=kwargs.get("reconcile_errors", 0)
        )
        
        # 添加时间戳
        if kwargs.get("start_time"):
            status.start_time = datetime.utcnow().isoformat() + "Z"
        if kwargs.get("completion_time"):
            status.completion_time = datetime.utcnow().isoformat() + "Z"
            
        # 更新状态条件
        new_condition = MLJobCondition(
            type=phase,
            status="True",
            reason=kwargs.get("reason"),
            message=message,
            last_transition_time=datetime.utcnow().isoformat() + "Z",
            last_update_time=datetime.utcnow().isoformat() + "Z"
        )
        
        # 保留最近的10个条件
        status.conditions = [new_condition] + status.conditions[:9]
        
        return status.dict(exclude_none=True)
    except Exception as e:
        logger.error(f"Failed to create MLJob status: {str(e)}")
        # 返回最小状态
        return {
            "phase": phase,
            "message": message,
            "observed_generation": kwargs.get("generation", 1)
        }

def get_job_age(meta: Dict[str, Any]) -> Optional[int]:
    """获取任务年龄(天)"""
    try:
        creation_time = meta.get("creationTimestamp")
        if creation_time:
            age = datetime.utcnow() - datetime.fromisoformat(creation_time.rstrip("Z"))
            return age.days
        return None
    except Exception:
        return None 