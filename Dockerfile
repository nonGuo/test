FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制项目依赖
COPY requirements.txt /app/
COPY api/requirements.txt /app/api/

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r api/requirements.txt

# 复制应用代码
COPY . /app

# 创建临时目录
RUN mkdir -p /tmp/test-case-api

# 设置环境变量文件
COPY api/.env.example /app/api/.env

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/api/v1/health')"

# 启动命令
CMD ["python", "api/run.py"]
