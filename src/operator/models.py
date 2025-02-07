"""CRD模型定义"""

from typing import Dict, Optional, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, validator

class ResourceRequirements(BaseModel):
    """资源需求"""
    requests: Dict[str, str] = Field(..., description="资源请求")
    limits: Optional[Dict[str, str]] = Field(None, description="资源限制")

class Container(BaseModel):
    """容器配置"""
    name: str = Field(..., description="容器名称")
    image: str = Field(..., description="容器镜像")
    command: Optional[List[str]] = Field(None, description="启动命令")
    args: Optional[List[str]] = Field(None, description="命令参数")
    resources: ResourceRequirements = Field(..., description="资源配置")

class PodTemplateSpec(BaseModel):
    """Pod模板规格"""
    containers: List[Container] = Field(..., description="容器配置")
    volumes: Optional[List[Dict]] = Field(None, description="存储卷配置")
    service_account: Optional[str] = Field(None, description="服务账号")
    node_selector: Optional[Dict[str, str]] = Field(None, description="节点选择器")
    tolerations: Optional[List[Dict]] = Field(None, description="容忍配置")

class ReplicaSpec(BaseModel):
    """副本规格"""
    replicas: int = Field(1, description="副本数量")
    template: PodTemplateSpec = Field(..., description="Pod模板")
    restart_policy: str = Field("Never", description="重启策略")

class TrainingSpec(BaseModel):
    """Training配置"""
    api_version: str = Field(..., description="Training Operator API版本")
    kind: str = Field(..., description="资源类型,如PyTorchJob或TFJob")
    spec: Dict[str, Any] = Field(..., description="完整的Training Operator配置")

class MLJobSpec(BaseModel):
    """MLJob规格"""
    job_id: str = Field(..., description="任务ID")
    project: str = Field(..., description="项目名称")
    owner: str = Field(..., description="所有者")
    description: Optional[str] = Field(None, description="任务描述")
    priority: Optional[int] = Field(0, ge=0, le=100, description="优先级,0-100")
    labels: Optional[Dict[str, str]] = Field(default_factory=dict, description="标签")
    training: TrainingSpec = Field(..., description="Training配置")

    @validator("job_id")
    def validate_job_id(cls, v):
        if not v or not v.strip():
            raise ValueError("job_id cannot be empty")
        return v

class MLJobCondition(BaseModel):
    """MLJob状态条件"""
    type: str = Field(..., description="条件类型")
    status: str = Field(..., description="条件状态")
    reason: Optional[str] = Field(None, description="状态原因")
    message: Optional[str] = Field(None, description="状态信息")
    last_transition_time: Optional[str] = Field(None, description="最后转换时间")
    last_update_time: Optional[str] = Field(None, description="最后更新时间")

class MLJobStatus(BaseModel):
    """MLJob状态"""
    phase: str = Field("Created", description="当前阶段")
    message: Optional[str] = Field(None, description="状态信息")
    reason: Optional[str] = Field(None, description="状态原因")
    training_status: Optional[Dict[str, Any]] = Field(None, description="Training Job状态")
    conditions: List[MLJobCondition] = Field(default_factory=list, description="状态条件")
    start_time: Optional[str] = Field(None, description="开始时间")
    completion_time: Optional[str] = Field(None, description="完成时间")
    observed_generation: Optional[int] = Field(None, description="观察到的资源版本")
    reconcile_errors: int = Field(0, description="调谐错误计数")

    @validator("phase")
    def validate_phase(cls, v):
        from .config import settings
        if v not in settings.JOB_PHASES.values():
            raise ValueError(f"phase must be one of {list(settings.JOB_PHASES.values())}")
        return v

class MLJob(BaseModel):
    """MLJob CRD"""
    api_version: str = Field(..., description="API版本")
    kind: str = Field("MLJob", description="资源类型")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    spec: MLJobSpec = Field(..., description="任务规格")
    status: Optional[MLJobStatus] = Field(None, description="任务状态")

class JobTemplateSpec(BaseModel):
    """Job模板规格"""
    metadata: Dict = Field(..., description="元数据")
    spec: Dict = Field(..., description="Job规格")

class MLJobTemplate(BaseModel):
    """ML任务模板"""
    pod_template: PodTemplateSpec = Field(..., description="Pod模板")
    job_template: JobTemplateSpec = Field(..., description="Job模板") 