FROM python:3.8-slim

WORKDIR /app

# 复制项目文件
COPY . .

# 安装依赖
RUN pip install --no-cache-dir -e .

# 设置环境变量
ENV PYTHONUNBUFFERED=1

# 运行operator
CMD ["python", "-m", "kubeflow_mini"] 