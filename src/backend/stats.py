"""项目资源统计

处理项目资源使用统计:
1. 计算项目资源使用情况
2. 统计项目任务状态
3. 计算资源使用率
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pony.orm import db_session, select
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from .models import Project, MLJob
from .config import settings

# 配置日志
logger = logging.getLogger(__name__)

# 初始化k8s客户端
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

k8s_api = client.CustomObjectsApi()

@db_session
def get_project_stats(project_id: int) -> Dict[str, Any]:
    """获取项目资源统计信息
    
    Args:
        project_id: 项目ID
        
    Returns:
        Dict: 项目统计信息，包括:
        - 资源配额和使用情况
        - 任务状态统计
        - 资源使用率
    """
    try:
        project = Project.get(id=project_id)
        if not project:
            return {}
            
        # 获取项目所有任务
        jobs = select(j for j in MLJob if j.project.id == project_id)[:]
        
        # 1. 资源配额和使用情况
        quotas = {
            "gpu": {
                "limit": project.gpu_limit,
                "used": sum(j.gpu_usage or 0 for j in jobs if j.status == "running"),
                "available": project.gpu_limit - sum(j.gpu_usage or 0 for j in jobs if j.status == "running")
            },
            "cpu": {
                "limit": project.cpu_limit,
                "used": sum(j.cpu_usage or 0 for j in jobs if j.status == "running"),
                "available": project.cpu_limit - sum(j.cpu_usage or 0 for j in jobs if j.status == "running")
            },
            "memory": {
                "limit": project.memory_limit,
                "used": _sum_memory_usage(jobs),
                "available": _calculate_available_memory(project.memory_limit, jobs)
            },
            "jobs": {
                "limit": project.max_jobs,
                "used": len(jobs),
                "available": project.max_jobs - len(jobs)
            }
        }
        
        # 2. 任务状态统计
        job_stats = {
            "total": len(jobs),
            "running": len([j for j in jobs if j.status == "running"]),
            "pending": len([j for j in jobs if j.status == "pending"]),
            "succeeded": len([j for j in jobs if j.status == "succeeded"]),
            "failed": len([j for j in jobs if j.status == "failed"]),
            "deleted": len([j for j in jobs if j.status == "deleted"]),
            "error": len([j for j in jobs if j.status == "error"])
        }
        
        # 3. 资源使用率
        usage_rates = {
            "gpu": _calculate_usage_rate(quotas["gpu"]["used"], quotas["gpu"]["limit"]),
            "cpu": _calculate_usage_rate(quotas["cpu"]["used"], quotas["cpu"]["limit"]),
            "memory": _calculate_usage_rate(
                _convert_memory_to_bytes(str(quotas["memory"]["used"])),
                _convert_memory_to_bytes(quotas["memory"]["limit"])
            ),
            "jobs": _calculate_usage_rate(quotas["jobs"]["used"], quotas["jobs"]["limit"])
        }
        
        # 4. 最近活动
        recent_activities = _get_recent_activities(jobs)
        
        return {
            "name": project.name,
            "quotas": quotas,
            "job_stats": job_stats,
            "usage_rates": usage_rates,
            "recent_activities": recent_activities,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get project stats: {str(e)}")
        return {}

def _sum_memory_usage(jobs: list) -> str:
    """计算内存使用总量"""
    try:
        total_bytes = 0
        for job in jobs:
            if job.status == "running" and job.memory_usage:
                total_bytes += _convert_memory_to_bytes(job.memory_usage)
        return _convert_bytes_to_memory(total_bytes)
    except:
        return "0"

def _calculate_available_memory(limit: str, jobs: list) -> str:
    """计算可用内存"""
    try:
        limit_bytes = _convert_memory_to_bytes(limit)
        used_bytes = sum(_convert_memory_to_bytes(j.memory_usage or "0") 
                        for j in jobs if j.status == "running")
        return _convert_bytes_to_memory(limit_bytes - used_bytes)
    except:
        return "0"

def _convert_memory_to_bytes(memory_str: str) -> int:
    """将内存字符串转换为字节数"""
    try:
        if not memory_str or memory_str == "0":
            return 0
            
        units = {
            'Ki': 1024,
            'Mi': 1024**2,
            'Gi': 1024**3,
            'Ti': 1024**4
        }
        
        for unit, multiplier in units.items():
            if memory_str.endswith(unit):
                return int(memory_str[:-len(unit)]) * multiplier
        return int(memory_str)
    except:
        return 0

def _convert_bytes_to_memory(bytes: int) -> str:
    """将字节数转换为可读的内存字符串"""
    try:
        for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti']:
            if bytes < 1024:
                return f"{bytes}{unit}"
            bytes /= 1024
        return f"{bytes}Ti"
    except:
        return "0"

def _calculate_usage_rate(used: float, limit: float) -> float:
    """计算使用率"""
    try:
        if limit <= 0:
            return 0.0
        return round((used / limit) * 100, 2)
    except:
        return 0.0

def _get_recent_activities(jobs: list, limit: int = 5) -> list:
    """获取最近的任务活动"""
    try:
        # 按更新时间排序
        sorted_jobs = sorted(
            jobs,
            key=lambda j: j.updated_at or datetime.min,
            reverse=True
        )
        
        activities = []
        for job in sorted_jobs[:limit]:
            activities.append({
                "job_id": job.job_id,
                "name": job.name,
                "status": job.status,
                "message": job.message,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None
            })
            
        return activities
    except:
        return [] 