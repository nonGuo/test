# API 设计文档

## 1. 概述

将长上下文处理逻辑封装为 Flask API 服务，提供测试设计生成的 HTTP 接口。

### 1.1 设计目标

- **简化调用**: 调用方只需上传文件，无需关心内部处理逻辑
- **完整处理**: 包含文档解析、智能分块、AI 调用、结果组装全流程
- **易于扩展**: 支持后续添加异步任务、缓存、监控等功能

### 1.2 架构图

```
┌─────────────────────────────────────────────────────────┐
│                    调用方 (Client)                       │
│  (测试用例生成 Agent / Web UI / CLI / 其他服务)            │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/REST API
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Flask API 服务 (api/app.py)                  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 路由层                                              │  │
│  │  - /api/v1/health                                  │  │
│  │  - /api/v1/generate-design                         │  │
│  │  - /api/v1/download-xmind                          │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 处理层                                              │  │
│  │  - 文件上传处理                                     │  │
│  │  - 文档解析 (RS/TS/Mapping)                        │  │
│  │  - 测试设计生成 (SmartChunkedGenerator)            │  │
│  │  - XMind 文件生成                                   │  │
│  └───────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 配置层                                              │  │
│  │  - 环境变量管理                                     │  │
│  │  - LLM 配置                                         │  │
│  │  - 日志管理                                         │  │
│  └───────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
            ┌─────────────────┐
            │   LLM 服务        │
            │ (通义千问/GPT)    │
            └─────────────────┘
```

---

## 2. 接口设计

### 2.1 接口列表

| 接口 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/api/v1/health` | GET | 健康检查 | 无 |
| `/api/v1/config` | GET | 获取配置 | 无 |
| `/api/v1/generate-design` | POST | 生成测试设计 | 无 (可扩展) |
| `/api/v1/download-xmind` | GET | 下载 XMind 文件 | 无 (可扩展) |

### 2.2 详细设计

#### POST /api/v1/generate-design

**请求格式**: `multipart/form-data`

**参数**:
| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `rs` | File | 是 | RS 设计文档 |
| `ts` | File | 是 | TS 表模型文档 |
| `mapping` | File | 是 | Mapping 规则文档 |
| `template` | File | 否 | XMind 模板文件 |
| `strategy` | String | 否 | 生成策略 |

**处理流程**:
```
1. 验证必需文件
   ↓
2. 验证文件格式
   ↓
3. 保存临时文件
   ↓
4. 加载 XMind 模板
   ↓
5. 初始化 LLM 客户端
   ↓
6. 解析文档 (RS/TS/Mapping)
   ↓
7. 生成测试设计 (SmartChunkedGenerator)
   ↓
8. 生成 XMind 文件
   ↓
9. 返回结果
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "design": {
      "root": {
        "title": "测试场景分析",
        "children": [...]
      },
      "source_tables": ["src_table"],
      "target_table": "dws_target",
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

---

## 3. 数据流

### 3.1 完整生成流程

```
Client 请求
    │
    ▼
Flask 接收文件
    │
    ▼
保存临时文件 ──────→ 临时目录 /tmp/xxx/
    │
    ▼
解析 RS 文档 ────────→ rs_content (文本)
    │
    ▼
解析 TS 文档 ────────→ ts_content (文本)
    │
    ▼
解析 Mapping ───────→ mapping_content (文本)
    │
    ▼
SmartChunkedGenerator
    │
    ├─→ 估算 token 数
    │       │
    │       ▼
    │   选择策略 (auto/full/by_branch/by_leaf)
    │       │
    │       ▼
    │   调用 LLM (1 次或多次)
    │       │
    │       ▼
    │   组装 TestDesign 对象
    │
    ▼
生成 XMind 文件
    │
    ▼
返回 JSON 响应
    │
    └─→ design (JSON)
    └─→ xmind_path (文件路径)
    └─→ stats (统计信息)
```

### 3.2 智能分块策略选择

```
输入内容估算
    │
    ▼
total_tokens = input_tokens + output_tokens
    │
    ├─ total < 80% max_input_tokens
    │       │
    │       ▼
    │   full (一次生成)
    │
    ├─ level_1_nodes <= 5
    │       │
    │       ▼
    │   by_branch (按分支生成)
    │
    └─ 其他
            │
            ▼
        by_leaf (按叶子生成)
```

---

## 4. 配置管理

### 4.1 环境变量

| 变量名 | 说明 | 默认值 | 示例 |
|--------|------|--------|------|
| `API_DEBUG` | 调试模式 | False | True |
| `API_HOST` | 监听地址 | 0.0.0.0 | 127.0.0.1 |
| `API_PORT` | 监听端口 | 5000 | 8080 |
| `UPLOAD_FOLDER` | 临时文件目录 | 系统临时目录 | /tmp/api |
| `MAX_CONTENT_LENGTH` | 最大上传大小 | 16MB | 33554432 |
| `LLM_PROVIDER` | LLM 提供商 | qwen | openai |
| `LLM_MODEL` | LLM 模型 | qwen-max | gpt-4 |
| `QWEN_API_KEY` | 通义千问 Key | - | sk-xxx |
| `OPENAI_API_KEY` | OpenAI Key | - | sk-xxx |
| `MAX_INPUT_TOKENS` | 最大输入 token | 8000 | 16000 |
| `GENERATION_STRATEGY` | 生成策略 | auto | by_branch |
| `LOG_LEVEL` | 日志级别 | INFO | DEBUG |

### 4.2 配置优先级

```
1. 环境变量 (最高优先级)
   ↓
2. .env 文件
   ↓
3. .env.example 默认值 (最低优先级)
```

---

## 5. 错误处理

### 5.1 错误响应格式

```json
{
  "success": false,
  "message": "错误描述",
  "code": "ERROR_CODE"
}
```

### 5.2 错误码定义

| 错误码 | HTTP 状态码 | 说明 |
|--------|-----------|------|
| `BAD_REQUEST` | 400 | 请求参数错误 |
| `FILE_MISSING` | 400 | 缺少必需文件 |
| `FILE_FORMAT_ERROR` | 400 | 文件格式不支持 |
| `FILE_TOO_LARGE` | 413 | 文件过大 |
| `API_KEY_NOT_CONFIGURED` | 500 | 未配置 API Key |
| `GENERATION_FAILED` | 500 | 生成失败 |
| `NOT_FOUND` | 404 | 资源不存在 |

---

## 6. 日志设计

### 6.1 日志级别

- **INFO**: 正常流程日志
- **WARNING**: 警告信息
- **ERROR**: 错误信息 (带堆栈)
- **DEBUG**: 调试信息

### 6.2 日志格式

```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### 6.3 示例输出

```
2026-03-10 12:00:00 - api.app - INFO - API 服务启动成功 - 版本：1.0.0
2026-03-10 12:01:00 - api.app - INFO - 开始生成测试设计 - 策略：auto
2026-03-10 12:01:01 - api.app - INFO - 解析 RS 文档...
2026-03-10 12:01:02 - api.app - INFO - 解析 TS 文档...
2026-03-10 12:01:03 - api.app - INFO - 解析 Mapping 文档...
2026-03-10 12:01:04 - api.app - INFO - 生成测试设计 (策略：auto)...
2026-03-10 12:01:20 - api.app - INFO - 测试设计生成完成 - 耗时：16.52s, 叶子节点数：10
```

---

## 7. 性能优化

### 7.1 当前性能

| 场景 | 测试点数 | 耗时 |
|------|---------|------|
| 小型项目 | < 20 | 5-10s |
| 中型项目 | 20-50 | 15-30s |
| 大型项目 | > 50 | 1-5min |

### 7.2 优化方向

1. **异步任务队列** (待实现)
   - 使用 Celery/RQ 处理长时间任务
   - 客户端轮询任务状态

2. **缓存机制** (待实现)
   - 缓存相同文档的解析结果
   - 缓存 LLM 响应

3. **并行处理**
   - 按叶子生成时使用并行模式
   - 文档解析可并行执行

4. **内容压缩**
   - 提取关键信息，减少 token 消耗
   - 压缩过长的文档内容

---

## 8. 安全考虑

### 8.1 当前安全措施

- 文件扩展名验证
- 文件大小限制
- 临时文件隔离存储

### 8.2 建议添加 (生产环境)

- API 认证 (JWT/Token)
- HTTPS 加密传输
- 请求频率限制
- 文件病毒扫描
- 敏感信息脱敏

---

## 9. 扩展计划

### 9.1 短期 (v1.1)

- [ ] 异步任务支持
- [ ] 任务进度查询
- [ ] API 认证

### 9.2 中期 (v1.2)

- [ ] 缓存机制
- [ ] 批量生成接口
- [ ] 测试用例生成接口

### 9.3 长期 (v2.0)

- [ ] Web UI
- [ ] 任务队列管理
- [ ] 多租户支持
- [ ] 监控告警

---

## 10. 调用示例

### 10.1 Python 调用

```python
import requests

files = {
    'rs': open('RS.docx', 'rb'),
    'ts': open('TS.docx', 'rb'),
    'mapping': open('Mapping.xlsx', 'rb')
}

response = requests.post(
    'http://localhost:5000/api/v1/generate-design',
    files=files,
    timeout=300
)

result = response.json()
print(f"生成成功：{result['success']}")
```

### 10.2 cURL 调用

```bash
curl -X POST http://localhost:5000/api/v1/generate-design \
  -F "rs=@RS.docx" \
  -F "ts=@TS.docx" \
  -F "mapping=@Mapping.xlsx" \
  -H "Authorization: Bearer <token>"
```

---

## 11. 总结

本 API 服务将长上下文处理逻辑完整封装，调用方只需上传文件即可获得测试设计结果。

**核心优势**:
- ✅ 调用简单，只需上传文件
- ✅ 智能分块，自动选择最优策略
- ✅ 完整处理，包含全流程
- ✅ 易于扩展，支持后续功能添加

**下一步**:
1. 配置环境变量
2. 启动服务测试
3. 集成到测试用例生成 Agent
