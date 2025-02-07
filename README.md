# Kubeflow Mini

一个基于Kopf和Kubeflow training-operator的简单机器学习平台。

## 功能特性

- 支持提交和管理机器学习训练任务
- 基于Kubeflow training-operator运行训练任务
- 使用Kopf operator进行任务生命周期管理

## 前置要求

- Kubernetes集群
- 已安装Kubeflow training-operator
- Python 3.8+

## 安装

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 安装Kubeflow training-operator：
```bash
kubectl apply -k "github.com/kubeflow/training-operator/manifests/overlays/standalone"
```

## 使用方法

1. 启动operator：
```bash
kopf run operator.py
```

2. 提交训练任务：
```bash
kubectl apply -f examples/pytorch-job.yaml
``` 