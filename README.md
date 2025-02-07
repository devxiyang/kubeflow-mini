# Kubeflow Mini

一个轻量级的机器学习任务管理工具，基于Kubeflow training-operator。

## 功能特性

- 管理PyTorch和TensorFlow训练任务
- 使用Kubernetes原生方式存储任务状态
- 提供简单的命令行工具
- 支持完整的training-operator配置

## 前置要求

- Kubernetes集群
- 已安装Kubeflow training-operator
- Python 3.8+

## 安装

1. 安装CRD和RBAC：
```bash
# 安装CRD
kubectl apply -f manifests/crd.yaml

# 安装RBAC
kubectl apply -f manifests/rbac.yaml
```

2. 部署operator：
```bash
# 构建并推送镜像（如果需要）
docker build -t your-registry/kubeflow-mini:latest .
docker push your-registry/kubeflow-mini:latest

# 部署operator
kubectl apply -f manifests/deployment.yaml
```

3. 安装命令行工具：
```bash
pip install -e .
```

## 使用方法

1. 提交训练任务：
```bash
kubectl apply -f examples/mnist-pytorch.yaml
```

2. 使用命令行工具：
```bash
# 查看所有任务
kubeflow-mini list

# 查看指定命名空间的任务
kubeflow-mini list -n default

# 查看特定任务的详细信息
kubeflow-mini get <任务名称> -n <命名空间> --show-training
```

## 配置说明

MLJob 资源包含两个主要部分：
1. 基本元数据：名称、命名空间等
2. Training配置：完整的training-operator配置

示例配置：
```yaml
apiVersion: kubeflow-mini.io/v1
kind: MLJob
metadata:
  name: mnist-pytorch
  namespace: default
spec:
  training:
    apiVersion: "kubeflow.org/v1"
    kind: PyTorchJob
    spec:
      pytorchReplicaSpecs:
        Worker:
          replicas: 1
          # ... training-operator的完整配置
```

## 项目结构

```
kubeflow-mini/
├── examples/                # 示例配置文件
├── manifests/              # Kubernetes资源定义文件
│   ├── crd.yaml           # 自定义资源定义
│   ├── rbac.yaml          # RBAC权限配置
│   └── deployment.yaml    # Operator部署配置
├── src/                    # 源代码
│   └── kubeflow_mini/
│       ├── cli/           # 命令行工具
│       ├── operator/      # Operator模块
│       └── __main__.py    # 主入口
└── README.md              # 项目文档
```

## 设计说明

kubeflow-mini 采用 Kubernetes 原生设计：
1. MLJob 资源包含完整的 training-operator 配置
2. Operator 自动创建和管理对应的 training-operator 资源
3. 状态存储在 Kubernetes etcd 中
4. 使用 RBAC 进行权限管理

这种设计的优点：
- 配置集中管理，避免多个资源文件
- 完整保留 training-operator 的所有功能
- 使用 Kubernetes 原生方式管理状态
- 支持标准的 Kubernetes RBAC

## 开发指南

1. 克隆代码库：
```bash
git clone https://github.com/yourusername/kubeflow-mini.git
cd kubeflow-mini
```

2. 创建虚拟环境：
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 安装开发依赖：
```bash
pip install -e ".[dev]"
```

## 许可证

MIT License 