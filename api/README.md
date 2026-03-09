# 数仓测试用例生成 API 文档

## 概述

提供长上下文测试设计生成的 HTTP API 服务，支持 RS/TS/Mapping 文档解析和测试设计自动生成。

**服务地址**: `http://localhost:5000`

---

## 快速开始

### 1. 配置环境变量

```bash
cd api
cp .env.example .env
# 编辑 .env 文件，配置 QWEN_API_KEY
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
python run.py
```

### 4. 验证服务

```bash
curl http://localhost:5000/api/v1/health
```

---

## API 接口

### 1. 健康检查

**接口**: `GET /api/v1/health`

**说明**: 检查服务状态

**响应示例**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "timestamp": "2026-03-10T12:00:00"
}
```

---

### 2. 生成测试设计（同步）

**接口**: `POST /api/v1/generate-design`

**说明**: 上传 RS/TS/Mapping 文档，生成测试设计

**请求参数** (multipart/form-data):

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| rs | File | 是 | RS 设计文档 (.docx/.pdf) |
| ts | File | 是 | TS 表模型文档 (.docx/.pdf) |
| mapping | File | 是 | Mapping 规则文档 (.xlsx/.csv) |
| template | File | 否 | XMind 模板文件 (默认使用内置模板) |
| strategy | String | 否 | 生成策略：auto/full/by_branch/by_leaf |

**请求示例**:
```bash
curl -X POST http://localhost:5000/api/v1/generate-design \
  -F "rs=@RS 样例.docx" \
  -F "ts=@TS 样例.docx" \
  -F "mapping=@mapping 样例.xlsx" \
  -F "template=@测试设计模板.xmind" \
  -F "strategy=auto"
```

**响应示例**:
```json
{
  "success": true,
  "data": {
    "design": {
      "root": {
        "title": "测试场景分析",
        "children": [
          {
            "title": "L0-数据结果检查",
            "children": [...]
          }
        ]
      },
      "source_tables": ["src_order"],
      "target_table": "dws_order_i",
      "mapping_rules": []
    },
    "xmind_path": "/tmp/xxx/test_design.xmind",
    "stats": {
      "strategy": "by_branch",
      "leaf_nodes": 10,
      "duration_seconds": 15.5,
      "llm_calls": 3
    }
  },
  "message": "测试设计生成成功"
}
```

**错误响应**:
```json
{
  "success": false,
  "message": "缺少必需文件：rs, ts, mapping"
}
```

---

### 3. 下载 XMind 文件

**接口**: `GET /api/v1/download-xmind?path=<文件路径>`

**说明**: 下载生成的 XMind 文件

**请求示例**:
```bash
curl -O http://localhost:5000/api/v1/download-xmind?path=/tmp/xxx/test_design.xmind
```

---

### 4. 获取配置信息

**接口**: `GET /api/v1/config`

**说明**: 查看当前服务配置（不包含敏感信息）

**响应示例**:
```json
{
  "version": "1.0.0",
  "llm_provider": "qwen",
  "llm_model": "qwen-max",
  "max_input_tokens": 8000,
  "strategy": "auto",
  "upload_folder": "/tmp/test-case-api",
  "max_content_length": 16777216
}
```

---

## Python 调用示例

### 基础调用

```python
import requests

# 准备文件
files = {
    'rs': open('RS 样例.docx', 'rb'),
    'ts': open('TS 样例.docx', 'rb'),
    'mapping': open('mapping 样例.xlsx', 'rb'),
    'template': open('测试设计模板.xmind', 'rb')
}

data = {
    'strategy': 'auto'
}

# 发送请求
response = requests.post(
    'http://localhost:5000/api/v1/generate-design',
    files=files,
    data=data
)

# 处理响应
if response.json()['success']:
    design = response.json()['data']['design']
    xmind_path = response.json()['data']['xmind_path']
    stats = response.json()['data']['stats']
    
    print(f"生成成功!")
    print(f"策略：{stats['strategy']}")
    print(f"叶子节点数：{stats['leaf_nodes']}")
    print(f"耗时：{stats['duration_seconds']}s")
else:
    print(f"生成失败：{response.json()['message']}")
```

### 下载 XMind 文件

```python
import requests

# 生成测试设计
response = requests.post(...)
xmind_path = response.json()['data']['xmind_path']

# 下载文件
download_url = f"http://localhost:5000/api/v1/download-xmind?path={xmind_path}"
download_resp = requests.get(download_url)

with open('test_design.xmind', 'wb') as f:
    f.write(download_resp.content)

print("XMind 文件已保存")
```

---

## cURL 调用示例

### 完整工作流

```bash
# 1. 生成测试设计
RESPONSE=$(curl -s -X POST http://localhost:5000/api/v1/generate-design \
  -F "rs=@RS 样例.docx" \
  -F "ts=@TS 样例.docx" \
  -F "mapping=@mapping 样例.xlsx" \
  -F "template=@测试设计模板.xmind")

# 2. 提取 XMind 文件路径
XMIND_PATH=$(echo $RESPONSE | jq -r '.data.xmind_path')

# 3. 下载 XMind 文件
curl -o test_design.xmind \
  "http://localhost:5000/api/v1/download-xmind?path=$XMIND_PATH"

echo "测试设计已保存到 test_design.xmind"
```

---

## 环境变量配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `API_DEBUG` | 调试模式 | False |
| `API_HOST` | 监听地址 | 0.0.0.0 |
| `API_PORT` | 监听端口 | 5000 |
| `UPLOAD_FOLDER` | 临时文件目录 | 系统临时目录 |
| `MAX_CONTENT_LENGTH` | 最大上传大小 | 16MB |
| `LLM_PROVIDER` | LLM 提供商 | qwen |
| `LLM_MODEL` | LLM 模型 | qwen-max |
| `QWEN_API_KEY` | 通义千问 API Key | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `MAX_INPUT_TOKENS` | 最大输入 token 数 | 8000 |
| `GENERATION_STRATEGY` | 生成策略 | auto |
| `LOG_LEVEL` | 日志级别 | INFO |

---

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 413 | 文件过大 |
| 500 | 服务器内部错误 |
| 501 | 功能未实现 |

---

## 性能参考

| 项目规模 | 测试点数 | 推荐策略 | 预计耗时 |
|---------|---------|---------|---------|
| 小型 | < 20 | auto (full) | 5-10s |
| 中型 | 20-50 | auto (by_branch) | 15-30s |
| 大型 | > 50 | auto (by_leaf) | 1-5min |

**注意**: 实际耗时取决于 LLM 响应速度和网络状况

---

## 最佳实践

### 1. 超时设置

建议在客户端设置合理的超时时间：

```python
import requests

response = requests.post(
    'http://localhost:5000/api/v1/generate-design',
    files=files,
    timeout=300  # 5 分钟超时
)
```

### 2. 错误重试

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(total=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)

response = session.post(..., timeout=300)
```

### 3. 进度监控

对于大型项目，建议记录日志监控进度：

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

response = requests.post(...)
stats = response.json()['data']['stats']

logger.info(f"生成完成：{stats['leaf_nodes']}个节点，耗时{stats['duration_seconds']}s")
```

---

## 常见问题

### Q: 上传文件失败怎么办？

A: 检查以下几点：
1. 文件大小是否超过 `MAX_CONTENT_LENGTH`
2. 文件格式是否支持 (docx/xlsx/xmind)
3. 文件名是否包含特殊字符

### Q: LLM 调用失败怎么办？

A: 检查：
1. API Key 是否正确配置
2. 网络连接是否正常
3. LLM 服务是否可用

### Q: 如何调整生成策略？

A: 两种方式：
1. 请求时指定 `strategy` 参数
2. 修改环境变量 `GENERATION_STRATEGY`

### Q: 临时文件会保留吗？

A: 不会。临时文件存储在系统临时目录，建议定期清理。

---

## 版本历史

### v1.0.0 (2026-03-10)
- ✅ 基础 API 服务
- ✅ 同步生成测试设计
- ✅ 文件上传和下载
- ✅ 配置管理
- ⏳ 异步任务（待实现）
