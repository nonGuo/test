# 数仓测试用例生成工具

AI 辅助生成数仓 (DWS 数据库) 测试用例的工具，支持两阶段生成流程，**模板调整无需修改代码**。

## 功能特点

- **阶段一**: AI 基于 RS/TS/Mapping 文档生成测试设计 (XMind)
- **阶段二**: 基于确认后的测试设计生成完整测试用例 (Excel + SQL)
- **支持人工干预**: 测试人员可在阶段一审查/修改测试设计
- **标准化输出**: 按企业模板生成测试设计和用例
- **动态模板适配**: 支持 XMind 模板动态调整，无需修改代码
- **REST API 服务**: 支持 HTTP 调用，易于集成到其他系统

---

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 初始化项目配置
python -m cli.main init
```

### 2. 配置 API Key

```bash
# 复制环境变量示例
cp .env.example .env

# 编辑 .env 文件，配置 API Key
# QWEN_API_KEY=your_qwen_api_key_here
# 或
# OPENAI_API_KEY=your_openai_api_key_here
```

### 3. 样例代码

#### 方式一：使用 CLI 命令

```bash
# 阶段一：生成测试设计
python -m cli.main generate-design \
    --rs RS 样例.docx \
    --ts TS 样例.docx \
    --mapping mapping 样例.xlsx \
    --template 测试设计模板.xmind \
    --output output/test_design.xmind

# 阶段二：生成测试用例
python -m cli.main generate-testcases \
    --xmind output/test_design.xmind \
    --ts TS 样例.docx \
    --mapping mapping 样例.xlsx \
    --output output/test_cases.xlsx
```

#### 方式二：使用 Python API

```python
# -*- coding: utf-8 -*-
"""
快速开始示例：使用 Python API 生成测试设计
"""
from core.ai import LLMClientFactory
from core.parser.document_parser import RSParser, TSParser
from core.parser import MappingParser
from core.analyzer import DesignGenerator
from core.generator import XMindGenerator, TestCaseExporter, SQLGenerator
from core.models import TestCase, TestCaseSuite

# ========== 1. 初始化 LLM 客户端 ==========
llm_client = LLMClientFactory.create(
    provider="qwen",      # 或 "openai"
    model="qwen-max"      # 或 "gpt-4"
)

# ========== 2. 解析输入文档 ==========
# 解析 RS 文档（提取测试要点）
rs_parser = RSParser()
rs_result = rs_parser.parse("RS 样例.docx")
rs_content = rs_parser.to_prompt_content(rs_result)
print(f"RS 测试要点：{rs_result['test_points']}")

# 解析 TS 文档（提取表元数据）
ts_parser = TSParser()
ts_result = ts_parser.parse("TS 样例.docx", llm_client=llm_client)
ts_content = ts_parser.to_prompt_content(ts_result)
print(f"目标表：{ts_result['interface_table'].table_name if ts_result['interface_table'] else 'N/A'}")

# 解析 Mapping 文档（提取字段映射）
mapping_parser = MappingParser()
mapping_result = mapping_parser.parse("mapping 样例.xlsx")
print(f"字段映射数：{len(mapping_result['field_mappings'])}")

# ========== 3. 生成测试设计 ==========
design_generator = DesignGenerator(
    llm_client=llm_client,
    template_path="测试设计模板.xmind",
    strategy="auto"  # 自动选择最优策略
)

design = design_generator.generate(
    rs_content=rs_content,
    ts_content=ts_content,
    mapping_content=str(mapping_result)
)

print(f"测试设计叶子节点数：{len(design.get_all_leaf_nodes())}")

# ========== 4. 导出 XMind ==========
xmind_gen = XMindGenerator(template_path="测试设计模板.xmind")
xmind_gen.generate(design, "output/my_test_design.xmind")
print("测试设计已保存：output/my_test_design.xmind")

# ========== 5. 生成测试用例 ==========
# 创建测试用例集
suite = TestCaseSuite(
    name="订单测试用例集",
    target_table="dws_order_i",
    design_version="my_test_design.xmind"
)

# 添加测试用例
sql_gen = SQLGenerator()

case = TestCase(
    case_id="TC_0001",
    case_name="主键唯一性检查",
    category="功能测试",
    scene="字段检查",
    priority="high",
    description="验证主键 order_id 唯一",
    tables=["dws_order_i"],
    test_steps=sql_gen.generate("primary_key_unique", {
        "target_table": "dws_order_i",
        "pk_field": "order_id"
    }),
    expected_result="返回 0 条记录"
)
suite.add_case(case)

# 导出 Excel
exporter = TestCaseExporter()
exporter.export_to_excel(suite, "output/my_test_cases.xlsx")
print("测试用例已保存：output/my_test_cases.xlsx")
```

### 4. 运行端到端测试

```bash
# 运行完整测试
python test_e2e.py
```

**测试结果示例**：

```
============================================================
端到端测试开始
============================================================

测试 1: RS 解析器 ..................................... [PASS]
测试 2: TS 解析器 ..................................... [PASS]
测试 3: Mapping 解析器 ............................... [PASS]
测试 4: XMind 模板加载器 ............................. [PASS]
测试 5: LLM 客户端 ................................... [SKIP]
测试 6: XMind 生成器 .................................. [PASS]
测试 7: SQL 生成器 .................................... [PASS]
测试 8: 测试用例导出器 ................................ [PASS]
测试 9: 完整工作流 .................................... [PASS]

总计：8 通过，0 失败，1 跳过
[SUCCESS] 所有测试通过
```

---

## API 服务

### 启动 API 服务

```bash
# 安装 API 依赖
pip install -r api/requirements.txt

# 配置环境变量
cd api
cp .env.example .env
# 编辑 .env，设置 QWEN_API_KEY

# 启动服务
python run.py
```

服务地址：`http://localhost:5000`

### API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/config` | GET | 获取配置 |
| `/api/v1/generate-design` | POST | 生成测试设计 |
| `/api/v1/download-xmind` | GET | 下载 XMind 文件 |

### 调用示例

```python
import requests

# 生成测试设计
files = {
    'rs': open('RS 样例.docx', 'rb'),
    'ts': open('TS 样例.docx', 'rb'),
    'mapping': open('mapping 样例.xlsx', 'rb')
}

response = requests.post(
    'http://localhost:5000/api/v1/generate-design',
    files=files,
    timeout=300
)

result = response.json()
print(f"叶子节点数：{result['data']['stats']['leaf_nodes']}")
```

**详细文档**: [api/README.md](api/README.md)

---

## Docker 部署

```bash
# 配置环境变量
export QWEN_API_KEY=sk-xxxxxxxxxxxxxxxx

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

**详细文档**: [api/DOCKER.md](api/DOCKER.md)

---

## 关键设计点

### 1. 两阶段工作流

```
┌─────────────────────────────────────────────────────────────┐
│ 阶段一：测试设计生成                                         │
│ RS + TS + Mapping → AI → XMind → 测试人员确认/修改           │
│                                                              │
│ 特点：动态加载 XMind 模板，按模板层级生成测试设计              │
│ 优势：模板调整无需修改代码！                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ 阶段二：测试用例生成                                         │
│ 已确认的 XMind → AI → 测试用例 (Excel + SQL 脚本)            │
└─────────────────────────────────────────────────────────────┘
```

**设计理念**：通过人工审查环节降低 AI 生成错误的风险，确保测试设计质量。

---

### 2. 动态模板适配

通过 `XMindTemplateLoader` 动态解析 XMind 模板结构，AI 严格按照模板层级生成测试设计。

**核心组件**：
- `XMindTemplateLoader`: 解析模板构建树状结构
- `DesignGenerator`: 统一的测试设计生成器
- `_validate_against_template()`: 验证生成结果与模板一致性

**模板调整场景**：

| 场景 | 操作 | 代码修改 |
|------|------|---------|
| 修改叶子节点文本 | 直接在 XMind 中编辑 | 无需 |
| 添加新测试分支 | 在 XMind 中添加子树 | 无需 |
| 调整层级深度 | 增加/减少节点层级 | 无需 |

**示例**：
```python
# 模板变更后，无需修改代码，直接重新运行即可
generator = DesignGenerator(llm_client, template_path="新模板.xmind")
design = generator.generate(rs, ts, mapping)
```

---

### 3. 智能分块生成

根据内容长度自动选择最优生成策略，解决 LLM 上下文限制问题。

**三种生成策略**：

| 策略 | 适用场景 | LLM 调用次数 | 特点 |
|------|---------|------------|------|
| **一次生成** | 小型项目 (< 20 测试点) | 1 次 | 整体一致性好 |
| **按分支生成** | 中型项目 (20-50 测试点) | 2-5 次 | 质量与效率平衡 |
| **按叶子生成** | 大型项目 (> 50 测试点) | 10-100 次 | 质量最高 |

**自动策略选择**：
```python
generator = DesignGenerator(
    llm_client=llm_client,
    template_path="template.xmind",
    strategy="auto"  # 自动选择最优策略
)
```

---

### 4. 分层元数据提取

解决 Mapping 规则复杂导致的上下文过长问题。

**三层元数据结构**：

```
Level 1: 元数据 (每个测试点都需要)
  - 字段名、类型、主键标识、是否度量字段

Level 2: 规则摘要 (按测试点类型选择)
  - 规则类型 (DIRECT/CALC/AGG)、来源表、复杂度

Level 3: 详细逻辑 (仅在生成 SQL 时需要)
  - 完整 SQL 表达式、关联条件、边界情况
```

**按需查询**：
```python
# 测试"主键检查"时，只加载主键相关信息
info = metadata_store.query_by_test_type("primary_key_check")
```

---

### 5. AI Prompt 工程

**结构化 Prompt 设计**：

```
请按照以下 XMind 模板结构生成测试设计：

└─ 测试场景分析 (分类节点)
  └─ L0-数据结果检查 (分类节点)
    └─ 表/视图检查 (分类节点)
      └─ 存在性与权限检查 (分类节点)
        └─ 验证 F/I/TMP 表是否存在 (叶子节点 - 需要生成具体测试点)

【业务背景】{rs_content}
【表模型】{ts_content}
【Mapping 规则】{mapping_content}
```

**Prompt 动态注入**：模板结构动态插入到 Prompt 中，支持模板变更。

---

### 6. 一致性验证

生成测试设计后自动验证与模板的一致性：

```python
def _validate_against_template(self, design: TestDesign) -> bool:
    # 获取模板的所有非叶子节点路径
    template_paths = {node.path for node in self.template_loader.node_map.values()
                      if not node.is_leaf}

    # 获取生成设计的所有节点路径
    design_paths = set()
    self._collect_design_paths(design.root, "", design_paths)

    # 检查缺失
    missing_paths = template_paths - design_paths

    if missing_paths:
        print("⚠️ 警告：生成的测试设计缺少以下模板节点:")
        for path in missing_paths:
            print(f"   - {path}")
        return False
    return True
```

---

### 7. 可扩展架构

**模块化设计**：

```
core/
├── analyzer/              # 分析器模块
│   ├── xmind_template_loader.py   # 模板加载器
│   ├── template_based_generator.py # 基于模板的生成器
│   ├── smart_generator.py         # 智能分块生成器
│   └── lightweight_generator.py    # 轻量级生成器
│
├── ai/                    # AI 模块
│   ├── ai_generator.py    # AI 生成器
│   └── llm_client.py      # LLM 客户端 (支持通义千问/GPT)
│
├── generator/             # 输出生成模块
│   ├── xmind_generator.py # XMind 文件生成
│   ├── sql_generator.py   # SQL 脚本生成
│   └── test_case_exporter.py # Excel 导出
│
├── parser/                # 输入解析模块
│   ├── document_parser.py # 文档解析器
│   ├── mapping_parser.py  # Mapping 解析器
│   └── mapping_processor.py # Mapping 处理器
│
└── models/                # 数据模型
    ├── test_design.py     # 测试设计模型
    └── test_case.py       # 测试用例模型
```

**扩展接口**：

```python
# 添加新的 LLM 提供商
class CustomLLMClient(BaseLLMClient):
    def generate(self, prompt: str) -> str:
        pass

# 添加新的文档解析器
class PDFParser(BaseParser):
    def parse(self, file_path: str) -> Any:
        pass
```

---

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

### 阶段一：生成测试设计

```bash
python cli/main.py generate-design \
    --rs docs/RS_设计文档.docx \
    --ts docs/TS_表模型.docx \
    --mapping docs/Mapping 规则.xlsx \
    --output test_design.xmind \
    --template templates/测试设计模板.xmind
```

输出：`test_design.xmind` 文件

### 审查和修改测试设计

1. 使用 XMind 打开生成的 `test_design.xmind`
2. 审查测试设计是否完整
3. 根据需要修改/补充/删除节点
4. 保存确认后的 XMind 文件

### 阶段二：生成测试用例

```bash
python cli/main.py generate-testcases \
    --xmind test_design_confirmed.xmind \
    --ts docs/TS_表模型.docx \
    --mapping docs/Mapping 规则.xlsx \
    --output test_cases.xlsx
```

输出：`test_cases.xlsx` 文件，包含：
- 用例编号、名称、分类、优先级
- 测试步骤 (SQL 脚本)
- 预期结果

---

## Python API

```python
from core.analyzer import DesignGenerator
from core.generator import XMindGenerator, TestCaseExporter
from core.ai import LLMClientFactory

# 创建 LLM 客户端
llm_client = LLMClientFactory.create("qwen", model="qwen-max")

# 生成测试设计（自动选择最优策略）
generator = DesignGenerator(
    llm_client=llm_client,
    template_path="templates/测试设计模板.xmind",
    strategy="auto"  # 可选：auto/full/by_branch/by_leaf
)
design = generator.generate(rs_content, ts_content, mapping_content)

# 导出 XMind
xmind_gen = XMindGenerator()
xmind_gen.generate(design, "output/test_design.xmind")
```

---

## 配置 AI 模型

在 `config/prompts.yaml` 中配置 AI 模型参数：

```yaml
llm:
  provider: qwen  # 或 openai
  model: qwen-max
  api_key: ${QWEN_API_KEY}
  temperature: 0.7
```

---

## XMind 节点规范

测试设计 XMind 遵循以下层级结构：

```
测试场景分析 (根节点)
├── L0-数据结果检查
│   ├── 表/视图检查
│   │   └─ 存在性与权限检查
│   │       └─ 目标存在性检查
│   │           └─ 验证 F/I/TMP 表是否存在 [priority:high]
│   └─ 字段检查
│       ├── 数据完整性检查
│       ├── 数据唯一性检查
│       └─ 数据有效性检查
│           └─ 字段功能检查
│               ├── 主外键类检查
│               └─ 度量类检查
└── L1-配置/调度作业检查
```

---

## 性能参考

| 项目规模 | 测试点数 | 推荐策略 | 生成时间 | LLM 调用 |
|---------|---------|---------|---------|---------|
| 小型 | < 20 | 一次生成 | 5-10s | 1 次 |
| 中型 | 20-50 | 按分支生成 | 15-30s | 2-5 次 |
| 大型 | > 50 | 按叶子生成 | 1-5min | 10-100 次 |

---

## 扩展开发

### 添加新的 SQL 模板

在 `config/sql_templates/` 目录下添加 `.sql` 文件：

```sql
-- custom_check.sql
SELECT COUNT(*) FROM {{ target_table }}
WHERE {{ condition }};
-- 预期：{{ expected_result }}
```

### 添加新的文档解析器

继承 `core.parser.BaseParser` 类实现新的解析器。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| `设计文档.md` | 完整架构设计文档 |
| `模板动态适配说明.md` | 模板动态适配技术细节 |
| `上下文问题解决方案.md` | LLM 上下文限制解决方案 |
| `Mapping 复杂逻辑处理方案.md` | Mapping 规则处理策略 |
| `生成策略分析.md` | AI 生成策略对比分析 |
| `api/README.md` | API 服务接口文档 |
| `api/快速开始.md` | API 服务快速上手 |

---

## 许可证

MIT License
