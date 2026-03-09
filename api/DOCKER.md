# 数仓测试用例生成 API - Docker 配置

## 快速开始

### 构建镜像

```bash
docker build -t test-case-api:latest .
```

### 运行容器

```bash
docker run -d \
  -p 5000:5000 \
  -e QWEN_API_KEY=your_api_key \
  -e LLM_PROVIDER=qwen \
  -e LLM_MODEL=qwen-max \
  -v /tmp/api-data:/tmp/test-case-api \
  --name test-case-api \
  test-case-api:latest
```

### 验证服务

```bash
curl http://localhost:5000/api/v1/health
```

### 查看日志

```bash
docker logs -f test-case-api
```

### 停止服务

```bash
docker stop test-case-api
docker rm test-case-api
```
