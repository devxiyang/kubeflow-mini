FROM python:3.8-slim

WORKDIR /app

# 复制项目文件
COPY src/backend backend/
COPY pyproject.toml .

# 安装依赖
RUN pip install --no-cache-dir -e .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"] 