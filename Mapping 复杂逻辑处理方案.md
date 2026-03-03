# Mapping 复杂加工逻辑处理方案

## 问题分析

### 现状挑战

1. **Mapping 规则数量多**
   - 小型表：10-30 个字段
   - 中型表：30-100 个字段
   - 大型表：100-500+ 个字段

2. **加工逻辑复杂度高**
   ```
   简单直取：source_field → target_field
   复杂计算：SUM(CASE WHEN condition THEN value ELSE 0 END) / NULLIF(COUNT(*), 0)
   多表关联：JOIN 5 个表，嵌套 3 层子查询
   ```

3. **上下文冗余严重**
   - 测试"主键检查"时，不需要知道"度量字段"的加工逻辑
   - 测试"表存在性"时，不需要任何字段级 Mapping
   - 但传统方式会把完整 Mapping 传给每个测试点

---

## 方案对比

### 方案 1: 完整 Mapping + 一次生成

```
输入：RS + TS + 完整 Mapping(500 字段) + 模板
  ↓
AI 生成测试设计
```

**问题**:
- ❌ 上下文爆炸 (500 字段 × 复杂逻辑 = 50K+ tokens)
- ❌ 注意力分散 (AI 难以聚焦)
- ❌ 成本高昂 (输入 token 多)
- ❌ 质量下降 (信息过载)

---

### 方案 2: 多 Agent 协作

```
┌─────────────────┐    请求字段逻辑    ┌─────────────────┐
│  测试设计 Agent  │ ────────────────→ │  Mapping 解释 Agent │
│  (不知道细节)    │ ←──────────────── │  (知道所有逻辑)   │
│                 │    返回字段逻辑    │                 │
└─────────────────┘                   └─────────────────┘
```

**优点**:
- ✅ 职责分离
- ✅ 测试设计 Agent 上下文小

**缺点**:
- ❌ 实现复杂 (需要 Agent 间通信)
- ❌ 延迟增加 (多次调用)
- ❌ 成本增加 (额外调用)
- ❌ 调试困难

**适用**: 超大型项目 (500+ 字段，100+ 测试点)

---

### 方案 3: 分层提取 + 按需加载 (推荐)

```
Mapping 文档
  ↓
预处理提取 (一次)
  ├── Level 1: 元数据 (字段名、类型、主键标识)
  ├── Level 2: 规则摘要 (规则类型、来源表)
  └── Level 3: 详细逻辑 (完整 SQL 表达式)
  
测试设计生成
  ├── 阶段 1: 使用 Level 1 元数据 → 生成测试框架
  ├── 阶段 2: 按测试点加载 Level 2 摘要 → 填充测试点
  └── 阶段 3: 按需加载 Level 3 详情 → 生成 SQL 脚本
```

**优点**:
- ✅ 上下文精简 (只传必要信息)
- ✅ 实现简单 (无需多 Agent)
- ✅ 成本低 (预处理一次)
- ✅ 质量好 (信息聚焦)

**适用**: 中小型项目 (10-100 字段)

---

### 方案 4: 混合策略 (最佳实践)

结合方案 2 和 3 的优势：

```
┌─────────────────────────────────────────────────────┐
│ 预处理阶段 (一次)                                    │
│ Mapping 文档 → 结构化存储 (JSON/数据库)              │
└─────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────┐
│ 测试设计生成 (单 Agent + 按需查询)                   │
│                                                      │
│ 生成框架时：使用元数据 (Level 1)                      │
│ 生成测试点时：使用规则摘要 (Level 2)                  │
│ 生成 SQL 时：查询详细逻辑 (Level 3)                   │
└─────────────────────────────────────────────────────┘
```

---

## 推荐方案：分层提取 + 按需查询

### 架构设计

```
MappingProcessor
    ↓ 解析
MappingMetadataStore
    ├── level1_metadata: 字段元数据
    ├── level2_summary: 规则摘要
    └── level3_details: 详细逻辑
    ↓ 按需查询
TestDesignGenerator
    ├── 阶段 1: 框架生成 (用 level1)
    ├── 阶段 2: 测试点填充 (用 level1+level2)
    └── 阶段 3: SQL 生成 (用 level3)
```

---

### 数据结构设计

```python
# Level 1: 元数据 (每个测试点都需要，体积小)
class FieldMetadata:
    name: str                    # 字段名
    table: str                   # 表名
    data_type: str               # 数据类型
    is_primary_key: bool         # 是否主键
    is_nullable: bool            # 是否可空
    is_measure: bool             # 是否度量字段
    business_category: str       # 业务分类 (客户/产品/交易...)

# Level 2: 规则摘要 (按测试点类型选择)
class RuleSummary:
    source_table: str            # 来源表
    source_field: str            # 来源字段
    rule_type: str               # 规则类型 (DIRECT/CALC/AGG/JAIN)
    complexity: str              # 复杂度 (LOW/MEDIUM/HIGH)
    involves_null_handling: bool # 是否涉及空值处理
    involves_case_when: bool     # 是否涉及 CASE WHEN
    aggregation_function: str    # 聚合函数 (SUM/COUNT/AVG...)

# Level 3: 详细逻辑 (仅在生成 SQL 时需要)
class DetailedLogic:
    full_expression: str         # 完整 SQL 表达式
    join_conditions: List[str]   # 关联条件
    filter_conditions: List[str] # 过滤条件
    business_rules: List[str]    # 业务规则描述
    edge_cases: List[str]        # 边界情况
```

---

### 实现示例

```python
class MappingMetadataStore:
    """Mapping 元数据存储"""
    
    def __init__(self):
        self.fields: Dict[str, FieldMetadata] = {}
        self.rules: Dict[str, RuleSummary] = {}
        self.details: Dict[str, DetailedLogic] = {}
    
    def get_level1_metadata(self, filter: dict = None) -> List[FieldMetadata]:
        """获取 Level 1 元数据 (支持过滤)"""
        if filter:
            # 例如：只获取主键字段
            if filter.get("is_primary_key"):
                return [f for f in self.fields.values() if f.is_primary_key]
            # 例如：只获取度量字段
            if filter.get("is_measure"):
                return [f for f in self.fields.values() if f.is_measure]
        return list(self.fields.values())
    
    def get_level2_summary(self, field_name: str) -> RuleSummary:
        """获取某个字段的规则摘要"""
        return self.rules.get(field_name)
    
    def get_level3_detail(self, field_name: str) -> DetailedLogic:
        """获取某个字段的详细逻辑"""
        return self.details.get(field_name)
    
    def query_by_test_type(self, test_type: str) -> dict:
        """根据测试类型查询相关信息"""
        if test_type == "primary_key_check":
            return {
                "fields": self.get_level1_metadata({"is_primary_key": True}),
                "rules": [self.rules[f.name] for f in self.get_level1_metadata({"is_primary_key": True})]
            }
        elif test_type == "measure_aggregation":
            return {
                "fields": self.get_level1_metadata({"is_measure": True}),
                "rules": [self.rules[f.name] for f in self.get_level1_metadata({"is_measure": True})]
            }
```

---

### 测试设计生成器 (精简版)

```python
class LightweightDesignGenerator:
    """轻量级测试设计生成器"""
    
    def __init__(self, llm_client, template_path, metadata_store):
        self.llm_client = llm_client
        self.template_loader = XMindTemplateLoader(template_path)
        self.metadata_store = metadata_store
    
    def generate_framework(self, rs_content: str) -> TestDesign:
        """
        阶段 1: 生成测试框架 (只用 RS + 模板)
        不需要 Mapping 细节
        """
        prompt = FRAMEWORK_PROMPT.format(
            rs_content=rs_content,
            template_guide=self.template_loader.get_template_guide()
        )
        
        response = self.llm_client.generate(prompt)
        return self._parse_response(response)
    
    def fill_test_points(self, design: TestDesign, 
                         test_type: str) -> TestDesign:
        """
        阶段 2: 填充特定类型的测试点
        只加载相关字段的摘要信息
        """
        # 查询相关字段
        related_info = self.metadata_store.query_by_test_type(test_type)
        
        # 构建精简 Prompt
        prompt = TEST_POINT_PROMPT.format(
            test_type=test_type,
            fields_summary=json.dumps([
                {"name": f.name, "rule_type": r.rule_type}
                for f, r in zip(related_info["fields"], related_info["rules"])
            ]),
            template_node=self._get_template_node_for_test_type(test_type)
        )
        
        response = self.llm_client.generate(prompt)
        return self._merge_results(design, response)
    
    def generate_test_sql(self, test_point: dict) -> str:
        """
        阶段 3: 生成测试 SQL
        按需加载详细逻辑
        """
        # 获取详细逻辑
        field_name = test_point.get("field_name")
        detail = self.metadata_store.get_level3_detail(field_name)
        
        # 基于详细逻辑生成 SQL
        prompt = SQL_GENERATION_PROMPT.format(
            field_name=field_name,
            full_expression=detail.full_expression,
            join_conditions=detail.join_conditions,
            test_requirement=test_point.get("requirement")
        )
        
        response = self.llm_client.generate(prompt)
        return self._parse_sql(response)
```

---

### Prompt 示例

#### 阶段 1: 框架生成 (无 Mapping)

```
你是一位数仓测试专家，请根据业务背景生成测试框架。

【业务背景】
{rs_content}

【测试设计模板】
{template_guide}

要求:
1. 生成测试设计的树形结构
2. 不需要具体字段细节
3. 标注每个叶子节点的测试类型

输出 JSON 格式。
```

**Token 消耗**: ~2K

---

#### 阶段 2: 测试点填充 (Level 1 + Level 2)

```
你是一位数仓测试专家，请为主键检查生成具体测试点。

【测试类型】主键检查

【相关字段摘要】
{
  "fields": [
    {"name": "ORDER_ID", "type": "STRING", "is_primary_key": true},
    {"name": "CUSTOMER_ID", "type": "STRING", "is_primary_key": true}
  ],
  "rules": [
    {"source": "ODS_ORDER.ORDER_ID", "rule_type": "DIRECT"},
    {"source": "ODS_ORDER.CUSTOMER_ID", "rule_type": "DIRECT"}
  ]
}

【模板节点】
验证主键字段空值率为 0
验证主键字段唯一

要求:
1. 为每个主键字段生成测试点
2. 标注优先级
3. 添加测试要点描述

输出 JSON 格式。
```

**Token 消耗**: ~3K

---

#### 阶段 3: SQL 生成 (Level 3)

```
你是一位 SQL 专家，请为以下字段生成测试 SQL。

【字段名】ORDER_AMT

【加工逻辑】
SUM(CASE WHEN status = 'COMPLETED' THEN amount ELSE 0 END)

【来源表】ODS_ORDER

【测试要求】验证聚合准确性

请生成验证 SQL：
```sql
SELECT 
  a.order_date,
  SUM(a.order_amt) AS target_sum,
  (SELECT SUM(CASE WHEN status = 'COMPLETED' THEN amount ELSE 0 END) 
   FROM ODS_ORDER b 
   WHERE b.order_date = a.order_date) AS source_sum
FROM DWS_ORDER_SUM a
GROUP BY a.order_date;
-- 预期：target_sum = source_sum
```
```

**Token 消耗**: ~1K

---

## 方案对比总结

| 方案 | 实现复杂度 | 上下文大小 | 成本 | 质量 | 适用场景 |
|------|----------|----------|------|------|---------|
| 完整 Mapping | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | 小型项目 (< 30 字段) |
| 多 Agent | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | 超大型项目 (500+ 字段) |
| 分层提取 | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | 中型项目 (30-100 字段) |
| 混合策略 | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | 所有场景 ⭐ |

---

## 推荐实施路线

### 阶段 1: 基础版本 (当前)

```
完整 Mapping → AI → 测试设计
```

适用：当前模板 (10 个测试点，字段数<30)

---

### 阶段 2: 分层提取 (字段 30-100)

```
Mapping → 预处理 → 元数据存储
  ↓
测试设计生成 → 按需查询元数据
```

---

### 阶段 3: 多 Agent 协作 (字段 100+)

```
┌──────────────┐     查询     ┌──────────────┐
│ 设计协调 Agent │ ←─────────→ │ Mapping Agent │
└──────────────┘              └──────────────┘
       ↓
┌──────────────┐
│  SQL 生成 Agent │
└──────────────┘
```

---

## 结论

**对于当前项目，推荐使用"分层提取 + 按需查询"方案**：

1. ✅ 实现简单 (无需多 Agent 通信)
2. ✅ 上下文精简 (只传必要信息)
3. ✅ 成本低 (预处理一次)
4. ✅ 可扩展 (未来可升级到多 Agent)

**实施步骤**:
1. 实现 MappingProcessor (解析 Mapping 文档)
2. 实现 MappingMetadataStore (存储分层数据)
3. 修改 TestDesignGenerator (按需查询)
4. 优化 Prompt (使用精简信息)
