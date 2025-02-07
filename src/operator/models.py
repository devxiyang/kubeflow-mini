"""CRD模型定义"""

from typing import Dict, Optional, Any
from pydantic import BaseModel, Field

class TrainingSpec(BaseModel):
    """Training配置,支持PyTorch和TensorFlow"""
    api_version: str = Field(..., description="Training Operator API版本")
    kind: str = Field(..., description="资源类型,如PyTorchJob或TFJob")
    spec: Dict[str, Any] = Field(..., description="完整的Training Operator配置")

class MLJobSpec(BaseModel):
    """MLJob规格"""
    job_id: str = Field(..., description="任务ID")
    project: str = Field(..., description="项目名称")
    owner: str = Field(..., description="所有者")
    description: Optional[str] = Field(None, description="任务描述")
    tags: Optional[list[str]] = Field(default_factory=list, description="标签")
    priority: Optional[int] = Field(0, description="优先级,0-100")
    training: TrainingSpec = Field(..., description="Training配置")

class MLJobStatus(BaseModel):
    """MLJob状态"""
    phase: str = Field("Created", description="当前阶段")
    message: Optional[str] = Field(None, description="状态信息")
    reason: Optional[str] = Field(None, description="状态原因")
    training_status: Optional[Dict[str, Any]] = Field(None, description="Training Job状态")
    conditions: Optional[list[Dict[str, Any]]] = Field(default_factory=list, description="状态条件")
    start_time: Optional[str] = Field(None, description="开始时间")
    completion_time: Optional[str] = Field(None, description="完成时间")

class MLJob(BaseModel):
    """MLJob CRD"""
    api_version: str = Field(..., description="API版本")
    kind: str = Field(..., description="资源类型")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    spec: MLJobSpec = Field(..., description="任务规格")
    status: Optional[MLJobStatus] = Field(None, description="任务状态")

class PodTemplateSpec(BaseModel):
    """Pod模板规格"""
    containers: List[Dict] = Field(..., description="容器配置")
    volumes: Optional[List[Dict]] = Field(None, description="存储卷配置")
    service_account: Optional[str] = Field(None, description="服务账号")
    node_selector: Optional[Dict[str, str]] = Field(None, description="节点选择器")
    tolerations: Optional[List[Dict]] = Field(None, description="容忍配置")

class JobTemplateSpec(BaseModel):
    """Job模板规格"""
    metadata: Dict = Field(..., description="元数据")
    spec: Dict = Field(..., description="Job规格")

class MLJobTemplate(BaseModel):
    """ML任务模板"""
    pod_template: PodTemplateSpec = Field(..., description="Pod模板")
    job_template: JobTemplateSpec = Field(..., description="Job模板") 