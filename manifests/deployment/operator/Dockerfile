FROM python:3.8-slim

WORKDIR /app

# 复制项目文件
COPY src/operator operator/
COPY pyproject.toml .
COPY ./config.yaml /etc/kubeflow-mini/config.yaml

# 安装依赖
RUN pip install --no-cache-dir -e .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV KOPF_STANDALONE=1
ENV CONFIG_FILE=/etc/kubeflow-mini/config.yaml

# 启动operator
CMD ["python", "-m", "operator"] 