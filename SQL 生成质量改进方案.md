# SQL 生成质量改进方案

## 📊 当前问题分析

### 原有 SQL 生成的问题

1. **模板过于简单** - 只有 10 个基础模板，缺乏复杂场景覆盖
2. **字段提取不准确** - `_extract_field()` 方法过于简单，依赖硬编码
3. **缺乏 Mapping 规则利用** - 没有充分利用 Mapping 中的转换规则生成针对性 SQL
4. **SQL 复杂度不足** - 无法处理 CASE WHEN、多表关联、复杂计算等场景
5. **预期结果不精确** - 预期结果都是通用描述，缺乏量化指标
6. **缺少质量验证** - 没有 SQL 质量评估和优化机制

---

## ✅ 改进方案实施

### 方案 1: 增强 SQL 模板库 (已完成)

**文件**: `core/generator/sql_generator_v2.py`

#### 新增 SQL 模板 (23 个 → 原有 10 个)

| 类别 | 模板数量 | 新增模板 |
|------|---------|---------|
| 表级别检查 | 3 | `table_row_count`, `table_primary_key_completeness` |
| 字段级别检查 | 3 | `field_precision_check`, `enum_value_check` |
| 主键/外键检查 | 3 | `foreign_key_referential_integrity` |
| 数据一致性检查 | 3 | `direct_aggregation_consistency`, `calculated_field_validation` |
| 度量值检查 | 3 | `measure_non_negative`, `measure_outlier_check` |
| 空值检查 | 2 | `required_field_not_null` |
| 数据分布检查 | 2 | `data_duplication_check` |
| 复杂规则检查 | 4 | `case_when_rule_validation`, `multi_join_consistency`, `data_freshness_check`, `partition_completeness` |

#### 改进点

1. **更精确的预期结果** - 根据参数动态生成预期结果
2. **质量评分机制** - 每个 SQL 都有质量评分 (0-100)
3. **警告系统** - 检测潜在问题并生成警告
4. **CTE 支持** - 使用 WITH 子句提高复杂查询可读性

#### 使用示例

```python
from core.generator.sql_generator_v2 import SQLGeneratorV2

generator = SQLGeneratorV2()

# 生成主键唯一性检查 SQL
result = generator.generate(
    check_type="primary_key_unique",
    params={
        "target_table": "dws_order_f",
        "pk_field": "order_id"
    }
)

print(result.sql)
# 输出:
# -- 测试：验证主键唯一性
# SELECT
#     order_id AS pk_value,
#     COUNT(*) AS duplicate_cnt
# FROM dws_order_f
# GROUP BY order_id
# HAVING COUNT(*) > 1
# ORDER BY duplicate_cnt DESC
# LIMIT 100;
# -- 预期：返回 0 条记录，主键 order_id 唯一性验证通过

print(f"质量评分：{result.quality_score * 100:.1f}")  # 100.0
print(f"预期结果：{result.expected_result}")
```

---

### 方案 2: 基于 Mapping 规则生成 SQL (已完成)

**文件**: `core/generator/mapping_sql_generator.py`

#### Mapping 规则类型与 SQL 模板映射

| 规则类型 | 子类型 | SQL 模板 | 适用场景 |
|---------|-------|---------|---------|
| **DIRECT** (直取) | default | `direct_single_field` | 直接复制源字段 |
| | with_filter | `direct_with_filter` | 带过滤条件的直取 |
| **CALC** (计算) | default | `calc_basic` | 四则运算 |
| | with_null_handling | `calc_with_null_handling` | 含空值处理的计算 |
| **AGG** (聚合) | SUM | `agg_sum` | 求和聚合 |
| | COUNT | `agg_count` | 计数聚合 |
| | AVG | `agg_avg` | 平均值聚合 |
| **CASE** (条件) | with_else | `case_when_with_else` | 含 ELSE 的 CASE WHEN |
| | without_else | `case_when_basic` | 不含 ELSE 的 CASE WHEN |
| **JOIN** (关联) | single | `join_single` | 单表关联 |
| | multiple | `join_multiple` | 多表关联 |
| **FUNC** (函数) | string | `func_string` | 字符串函数 |
| | date | `func_date` | 日期函数 |
| **CONST** (常量) | default | `const_value` | 常量赋值 |
| **SUBQ** (子查询) | correlated | `subquery_correlated` | 相关子查询 |

#### 使用示例

```python
from core.generator.mapping_sql_generator import MappingBasedSQLGenerator

generator = MappingBasedSQLGenerator()

# DIRECT 规则 - 直取字段
mapping_rule = {
    "target_field": "order_id",
    "source_field": "order_id",
    "target_table": "dws_order_f",
    "source_table": "ods_order",
    "transform_rule": "order_id",
    "rule_type": "DIRECT",
    "join_key": "order_id"
}

result = generator.generate_from_mapping(mapping_rule)
print(result.sql)
# 输出:
# -- 测试：验证直取字段 order_id 与源数据一致
# -- 规则类型：DIRECT (直取)
# -- 转换规则：order_id
# SELECT
#     a.order_id AS target_value,
#     b.order_id AS source_value,
#     COUNT(*) AS diff_cnt
# FROM dws_order_f a
# INNER JOIN ods_order b
#     ON a.order_id = b.order_id
# WHERE a.order_id <> b.order_id
#    OR (a.order_id IS NULL AND b.order_id IS NOT NULL)
#    OR (a.order_id IS NOT NULL AND b.order_id IS NULL)
# GROUP BY a.order_id, b.order_id
# ORDER BY diff_cnt DESC
# LIMIT 100;
# -- 预期：返回 0 条记录

print(f"规则类型：{result.rule_type}")  # DIRECT
print(f"复杂度：{result.complexity}")   # LOW
```

#### 批量生成示例

```python
# 批量生成 SQL
mapping_rules = [
    {
        "target_field": "order_id",
        "source_field": "order_id",
        "target_table": "dws_order_f",
        "source_table": "ods_order",
        "transform_rule": "order_id",
        "rule_type": "DIRECT",
        "join_key": "order_id"
    },
    {
        "target_field": "total_amount",
        "source_field": "amount",
        "target_table": "dws_order_f",
        "source_table": "ods_order",
        "transform_rule": "amount + tax",
        "rule_type": "CALC"
    },
    {
        "target_field": "order_amt_sum",
        "source_field": "order_amt",
        "target_table": "dws_customer_sum_f",
        "source_table": "dws_order_f",
        "transform_rule": "SUM(order_amt)",
        "rule_type": "AGG",
        "group_fields": ["customer_id", "dt"]
    }
]

results = generator.generate_batch_from_mapping(mapping_rules)
for i, result in enumerate(results, 1):
    print(f"[{i}] {result.target_field}: {result.rule_type} ({result.complexity})")
```

---

### 方案 3: SQL 质量验证与优化 (已完成)

**文件**: `core/generator/sql_validator.py`

#### 质量验证维度

| 维度 | 权重 | 检查项 |
|------|------|-------|
| **语法正确性** | 30% | SELECT/FROM 完整性、括号匹配、CASE WHEN 配对、引号匹配 |
| **完整性** | 30% | 注释说明、预期结果、测试目的 |
| **性能** | 20% | SELECT * 检测、函数索引失效、LIMIT 限制 |
| **安全性** | 10% | DROP/DELETE/UPDATE检测、EXEC 调用检测 |
| **可读性** | 10% | 行长度、别名使用、格式化 |

#### 性能反模式检测

```python
PERFORMANCE_ANTI_PATTERNS = [
    (r"SELECT\s+\*", "避免 SELECT *，明确指定需要的列"),
    (r"\bWHERE\b.*\bOR\b.*\b=\b", "OR 条件可能导致索引失效"),
    (r"LIKE\s*['\"]%", "前缀模糊查询可能导致全表扫描"),
    (r"NOT\s+IN\s*\(", "NOT IN 可能导致性能问题，考虑使用 NOT EXISTS"),
    (r"YEAR\s*\(\s*\w+\s*\)", "对字段使用函数可能导致索引失效"),
    # ... 更多检测
]
```

#### 使用示例

```python
from core.generator.sql_validator import SQLValidator, SQLOptimizer

validator = SQLValidator()
optimizer = SQLOptimizer()

# 验证 SQL 质量
sql = """
-- 测试：验证主键 order_id 唯一性
SELECT
    order_id AS pk_value,
    COUNT(*) AS duplicate_cnt
FROM dws_order_f
GROUP BY order_id
HAVING COUNT(*) > 1
ORDER BY duplicate_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""

result = validator.validate(sql)
print(f"SQL 分数：{result.score:.1f}")      # 100.0
print(f"是否有效：{result.is_valid}")       # True
print(f"指标：{result.metrics}")
# {'length': 197, 'line_count': 12, 'select_count': 1, 
#  'join_count': 0, 'where_count': 0, 'group_by_count': 1, 
#  'order_by_count': 1, 'case_when_count': 0, 'subquery_count': 0, 
#  'comment_count': 2}

# 批量验证并生成报告
sql_list = [...]  # SQL 列表
results = validator.validate_batch(sql_list)
report = validator.get_validation_report(results)
print(report)

# 优化 SQL
bad_sql = "SELECT * FROM users WHERE id = 1"
optimized = optimizer.optimize(bad_sql)
print(optimized)
# SELECT /* 请指定具体列 */ *
# FROM users
# WHERE id = 1
# LIMIT 1000;
```

---

## 📁 新增文件清单

```
D:\Projects\ai\test\
├── core\generator\
│   ├── sql_generator_v2.py          # 增强版 SQL 生成器 (23 个模板)
│   ├── mapping_sql_generator.py     # 基于 Mapping 规则的 SQL 生成器
│   └── sql_validator.py             # SQL 质量验证器
│
├── config\
│   └── sql_config.yaml              # SQL 生成配置文件
│
└── test_sql_generator_v2.py         # 测试脚本
```

---

## 🧪 测试结果

### 测试覆盖率

| 测试项 | 状态 | 说明 |
|--------|------|------|
| SQLGeneratorV2 | ✅ 通过 | 5 个子测试全部通过 |
| MappingBasedSQLGenerator | ✅ 通过 | 5 个子测试全部通过 |
| SQLValidator | ✅ 通过 | 4 个子测试全部通过 |
| SQLOptimizer | ✅ 通过 | 2 个子测试全部通过 |
| 质量对比分析 | ✅ 通过 | 3 个场景对比完成 |

### 质量对比结果

| 场景 | 分数 | 问题数 | 建议数 |
|------|------|--------|--------|
| 主键唯一性检查 | 100.0 | 0 | 0 |
| 直取字段一致性检查 | 100.0 | 0 | 1 |
| 度量值汇总检查 | 100.0 | 0 | 1 |

---

## 🚀 使用指南

### 快速开始

```python
# 1. 导入模块
from core.generator.sql_generator_v2 import SQLGeneratorV2
from core.generator.mapping_sql_generator import MappingBasedSQLGenerator
from core.generator.sql_validator import SQLValidator

# 2. 创建生成器
generator = SQLGeneratorV2()
mapping_generator = MappingBasedSQLGenerator()
validator = SQLValidator()

# 3. 基于测试用例生成 SQL
test_case = {
    "case_name": "验证主键 order_id 唯一性",
    "tables": ["dws_order_f"],
    "description": "验证主键字段 order_id 唯一"
}
result = generator.generate_for_test_case(test_case)
print(result.sql)

# 4. 基于 Mapping 规则生成 SQL
mapping_rule = {
    "target_field": "order_id",
    "source_field": "order_id",
    "target_table": "dws_order_f",
    "source_table": "ods_order",
    "transform_rule": "order_id",
    "rule_type": "DIRECT",
    "join_key": "order_id"
}
result = mapping_generator.generate_from_mapping(mapping_rule)
print(result.sql)

# 5. 验证 SQL 质量
validation = validator.validate(result.sql)
print(f"质量分数：{validation.score:.1f}")
if validation.suggestions:
    print(f"优化建议：{validation.suggestions}")
```

### 集成到现有流程

修改 `core/generator/test_case_exporter.py` 中的 SQL 生成逻辑:

```python
# 原来
from core.generator import SQLGenerator

# 新版本
from core.generator.sql_generator_v2 import SQLGeneratorV2
from core.generator.mapping_sql_generator import MappingBasedSQLGenerator

# 使用增强版生成器
sql_generator = SQLGeneratorV2()
mapping_generator = MappingBasedSQLGenerator()

# 生成 SQL 时，优先使用 Mapping 规则
if mapping_info:
    result = mapping_generator.generate_from_mapping(mapping_rule)
    sql = result.sql
else:
    result = sql_generator.generate_for_test_case(test_case)
    sql = result.sql
```

---

## 📈 改进效果对比

| 指标 | 改进前 | 改进后 | 提升 |
|------|--------|--------|------|
| SQL 模板数量 | 10 | 23+ | +130% |
| 支持规则类型 | 3 | 8 | +167% |
| 预期结果精确度 | 通用描述 | 动态生成 | 显著提升 |
| 质量验证 | 无 | 5 维度评分 | 新增 |
| Mapping 规则利用 | 无 | 分层映射 | 新增 |
| 复杂场景支持 | 有限 | CASE WHEN/多表关联/子查询 | 显著提升 |

---

## 🔧 配置文件说明

**config/sql_config.yaml** 包含:

1. **SQL 模板配置** - 启用的模板列表
2. **Mapping 规则映射** - 规则类型到 SQL 模板的映射
3. **默认参数** - 容差、最小行数等
4. **字段类型检查** - 不同字段类型的推荐检查
5. **质量配置** - 最低质量分数、必须检查项
6. **预期结果模板** - 动态生成预期结果的模板

---

## 📝 下一步建议

1. **集成到 AI 生成流程** - 在 AI 生成测试用例后，使用新的 SQL 生成器优化 SQL
2. **扩展模板库** - 根据实际业务需求添加更多 SQL 模板
3. **SQL 执行验证** - 连接数据库实际执行 SQL，验证可执行性
4. **智能推荐** - 根据字段特征自动推荐最合适的检查类型
5. **性能基准** - 建立 SQL 性能基准，自动优化慢查询

---

## 💡 最佳实践

1. **优先使用 Mapping 规则生成** - 根据转换规则类型自动生成针对性 SQL
2. **质量分数低于 60 需优化** - 使用 SQLValidator 检测问题并优化
3. **添加详细注释** - 每个 SQL 都应包含测试目的和预期结果
4. **限制返回行数** - 所有查询都应添加 LIMIT 防止数据量过大
5. **使用 CTE 提高可读性** - 复杂查询使用 WITH 子句

---

**改进完成！SQL 生成质量显著提升！** 🎉
