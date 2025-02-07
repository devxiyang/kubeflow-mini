# Kubeflow Mini

一个轻量级的机器学习任务管理工具，基于Kubeflow training-operator。

## 功能特性

- 管理PyTorch和TensorFlow训练任务
- 使用SQLite数据库存储任务信息
- 提供简单的命令行工具
- 支持完整的training-operator配置

## 前置要求

- Kubernetes集群
- 已安装Kubeflow training-operator
- Python 3.8+
- SQLite3

## 安装

1. 从源码安装：
```bash
pip install -e .
```

2. 安装CRD：
```bash
kubectl apply -f manifests/crd.yaml
```

## 使用方法

1. 启动operator：
```bash
python -m kubeflow_mini
```

2. 提交训练任务：
```bash
kubectl apply -f examples/mnist-pytorch.yaml
```

3. 使用命令行工具：
```bash
# 查看所有任务
kubeflow-mini list

# 查看指定命名空间的任务
kubeflow-mini list --namespace default

# 查看指定状态的任务
kubeflow-mini list --status running

# 查看特定任务的详细信息
kubeflow-mini status <任务名称> <命名空间>
```

## 配置说明

MLJob 资源包含两个主要部分：
1. 基本信息：框架类型和版本
2. Training配置：完整的training-operator配置

示例配置：
```yaml
apiVersion: kubeflow-mini.io/v1
kind: MLJob
metadata:
  name: mnist-pytorch
  namespace: default
spec:
  framework: pytorch
  frameworkVersion: "1.13.1"
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
├── src/                    # 源代码
│   └── kubeflow_mini/
│       ├── cli/           # 命令行工具
│       ├── db/            # 数据库模块
│       ├── operator/      # Operator模块
│       └── __main__.py    # 主入口
└── README.md              # 项目文档
```

## 设计说明

kubeflow-mini 采用统一配置的设计：
1. MLJob 资源包含完整的 training-operator 配置
2. operator 自动创建和管理对应的 training-operator 资源
3. 数据库记录任务状态和历史信息

这种设计的优点：
- 配置集中管理，避免多个资源文件
- 完整保留 training-operator 的所有功能
- 自动同步任务状态
- 支持任务历史记录和查询

## 任务状态说明

- created: 任务已创建
- running: 任务正在运行
- completed: 任务已完成
- failed: 任务失败
- deleted: 任务已删除

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

4. 运行测试：
```bash
pytest tests/
```

## 许可证

MIT License 