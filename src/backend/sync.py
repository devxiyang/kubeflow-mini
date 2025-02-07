"""状态同步和资源清理

处理:
1. MLJob状态同步 - 从Kubernetes同步状态到数据库
2. 资源清理 - 清理过期和失败的资源
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pony.orm import db_session, select

from .models import MLJob
from .config import settings
from .k8s import get_mljob_status, delete_mljob_resource

# 配置日志
logger = logging.getLogger(__name__)

@db_session
def sync_job_status():
    """同步MLJob状态
    
    从Kubernetes同步状态到数据库:
    1. 获取需要同步的任务
    2. 获取Kubernetes中的状态
    3. 更新数据库记录
    """
    try:
        # 获取活跃任务
        active_jobs = select(j for j in MLJob if j.status not in ["succeeded", "failed", "deleted"])[:]
        
        for job in active_jobs:
            try:
                # 获取k8s状态
                k8s_status = get_mljob_status(job.name, job.namespace)
                
                if k8s_status:
                    # 更新状态
                    job.status = k8s_status.get("phase", "unknown").lower()
                    job.message = k8s_status.get("message")
                    job.training_status = str(k8s_status.get("training_status", {}))
                    job.updated_at = datetime.utcnow()
                    
                    # 更新时间
                    if job.status == "running" and not job.started_at:
                        job.started_at = datetime.utcnow()
                    elif job.status in ["succeeded", "failed"]:
                        job.completed_at = datetime.utcnow()
                        
                    # 更新资源使用情况
                    if "resources" in k8s_status:
                        resources = k8s_status["resources"]
                        job.gpu_usage = resources.get("gpu")
                        job.cpu_usage = resources.get("cpu")
                        job.memory_usage = resources.get("memory")
                        
                    # 重置错误计数
                    job.sync_errors = 0
                    
                else:
                    # 增加错误计数
                    job.sync_errors += 1
                    
                    # 如果错误次数过多,标记为失败
                    if job.sync_errors >= settings.SYNC_ERROR_THRESHOLD:
                        job.status = "failed"
                        job.message = "Failed to sync with Kubernetes resource"
                        job.completed_at = datetime.utcnow()
                    
            except Exception as e:
                logger.error(f"Failed to sync job {job.job_id}: {str(e)}")
                job.sync_errors += 1
                
    except Exception as e:
        logger.error(f"Failed to sync job status: {str(e)}")

@db_session
def cleanup_resources():
    """清理资源
    
    清理:
    1. 已完成且超过保留时间的任务
    2. 同步失败的任务
    3. 孤立的Kubernetes资源
    """
    try:
        # 计算截止时间
        cutoff_time = datetime.utcnow() - timedelta(days=settings.RESOURCE.max_job_age)
        
        # 获取需要清理的任务
        jobs_to_cleanup = select(j for j in MLJob if 
            # 已完成且超过保留时间
            ((j.status in ["succeeded", "failed", "deleted"] and j.completed_at < cutoff_time)) or
            # 同步错误次数过多
            (j.sync_errors >= settings.SYNC_ERROR_THRESHOLD)
        )[:]
        
        for job in jobs_to_cleanup:
            try:
                # 删除Kubernetes资源
                delete_mljob_resource(job.name, job.namespace)
                
                # 更新数据库状态
                job.status = "deleted"
                job.message = "Resource cleaned up"
                job.updated_at = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Failed to cleanup job {job.job_id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Failed to cleanup resources: {str(e)}")

def _should_cleanup_job(job: MLJob) -> bool:
    """检查任务是否需要清理"""
    # 已完成任务
    if job.status in ["succeeded", "failed", "deleted"]:
        if job.completed_at:
            age = datetime.utcnow() - job.completed_at
            return age.days >= settings.RESOURCE.max_job_age
    
    # 同步失败的任务
    if job.sync_errors >= settings.SYNC_ERROR_THRESHOLD:
        return True
        
    return False 