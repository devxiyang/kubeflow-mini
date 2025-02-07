# Kubeflow Mini

一个轻量级的机器学习任务管理工具，基于 Kubeflow training-operator。

## 功能特性

- 项目管理
  - 创建和管理机器学习项目
  - 设置项目资源配额（GPU、CPU、内存）
  - 项目成员管理
  - 项目资源使用统计

- ML 任务管理
  - 支持 PyTorch 和 TensorFlow 训练任务
  - 完整的 training-operator 配置支持
  - 任务状态监控和日志查看
  - 资源使用情况追踪

- Notebook 管理
  - 创建和管理 Jupyter Notebook 实例
  - 自动资源分配和回收
  - 租约管理（自动停止和续租）
  - 支持多种 Jupyter 镜像

## 系统架构

项目由三个主要组件组成：

1. Frontend (Next.js)
   - 现代化的 Web 界面
   - 响应式设计
   - 实时状态更新

2. Backend (FastAPI)
   - RESTful API
   - 用户认证和授权
   - 数据库管理
   - 资源配额控制

3. Operator (Kopf)
   - Kubernetes 原生集成
   - 自动化资源管理
   - 状态同步和监控

## 前置要求

- Kubernetes 集群 (1.20+)
- 已安装 Kubeflow training-operator
- Python 3.8+
- Node.js 18+
- Docker

## 快速开始

1. 克隆仓库：
```bash
git clone https://github.com/yourusername/kubeflow-mini.git
cd kubeflow-mini
```

2. 安装依赖：
```bash
# 后端依赖
cd src/backend
pip install -e .

# 前端依赖
cd ../frontend
npm install
```

3. 配置环境变量：
```bash
# 后端
cp .env.example .env
# 编辑 .env 文件设置必要的环境变量

# 前端
cd src/frontend
cp .env.example .env.local
# 编辑 .env.local 文件设置必要的环境变量
```

4. 启动服务：

开发模式：
```bash
# 后端
cd src/backend
uvicorn app:app --reload

# 前端
cd src/frontend
npm run dev

# operator
cd src/operator
kopf run operator.py
```

生产模式：
```bash
docker compose up -d
```

## 项目结构

```
kubeflow-mini/
├── src/
│   ├── frontend/          # Next.js 前端
│   ├── backend/          # FastAPI 后端
│   └── operator/         # Kubernetes Operator
├── manifests/           # Kubernetes 资源定义
│   ├── deployment/      # 部署配置
│   └── crd/            # 自定义资源定义
├── examples/           # 示例配置
└── docs/              # 文档
```

## API 文档

启动后端服务后，访问以下地址查看 API 文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 开发指南

1. 代码风格
   - 后端：使用 black 和 isort 进行格式化
   - 前端：使用 prettier 和 eslint
   - 提交前运行 pre-commit hooks

2. 测试
   - 后端：pytest
   - 前端：jest 和 React Testing Library
   - E2E：Cypress

3. 分支策略
   - main: 稳定版本
   - develop: 开发版本
   - feature/*: 新功能
   - fix/*: 错误修复

## 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建 Pull Request

## 许可证

MIT License 