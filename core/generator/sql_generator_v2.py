"""
SQL 测试脚本生成器 V2
增强版：基于 Mapping 规则分层生成 SQL

改进点:
1. 扩展 SQL 模板库，覆盖更多测试场景
2. 基于 Mapping 规则类型自动生成对应 SQL
3. 支持复杂表达式、CASE WHEN、多表关联
4. 生成更精确的预期结果
5. 支持 SQL 质量验证和优化
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from jinja2 import Template
import re


# ============== 增强的 SQL 模板库 ==============

SQL_TEMPLATES = {
    # ==================== 表级别检查 ====================
    
    # 1. 表存在性检查
    "table_exists": Template("""
-- 测试：验证目标表是否存在
SELECT COUNT(*) AS cnt
FROM {{ target_table }};
-- 预期：查询成功，cnt >= 0
"""),

    # 2. 表数据量检查
    "table_row_count": Template("""
-- 测试：验证表数据量是否合理
SELECT 
    COUNT(*) AS total_cnt,
    COUNT(DISTINCT dt) AS partition_cnt
FROM {{ target_table }}
{% if partition_condition %}WHERE {{ partition_condition }}{% endif %};
-- 预期：total_cnt >= {{ min_rows }}, partition_cnt >= {{ min_partitions }}
"""),

    # 3. 表主键完整性
    "table_primary_key_completeness": Template("""
-- 测试：验证主键完整性
SELECT 
    COUNT(*) AS total_cnt,
    COUNT({{ pk_field }}) AS pk_cnt,
    COUNT(*) - COUNT({{ pk_field }}) AS null_pk_cnt
FROM {{ target_table }};
-- 预期：null_pk_cnt = 0 (主键不能为空)
"""),

    # ==================== 字段级别检查 ====================
    
    # 4. 字段完整性检查
    "field_completeness": Template("""
-- 测试：验证字段定义与 Mapping 一致
SELECT
    COLUMN_NAME AS field_name,
    DATA_TYPE AS data_type,
    CHARACTER_MAXIMUM_LENGTH AS char_max_len,
    NUMERIC_PRECISION AS numeric_precision,
    NUMERIC_SCALE AS numeric_scale
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = '{{ target_table }}'
  AND TABLE_SCHEMA = '{{ target_schema | default("dbo") }}'
ORDER BY ORDINAL_POSITION;
-- 预期：字段数量={{ expected_field_count }}, 各字段类型与 Mapping 定义一致
"""),

    # 5. 字段精度检查
    "field_precision_check": Template("""
-- 测试：验证字段精度是否符合要求
SELECT
    {{ field }} AS field_value,
    LENGTH(CAST({{ field }} AS VARCHAR)) AS actual_length,
    {{ max_length }} AS max_allowed_length
FROM {{ target_table }}
WHERE LENGTH(CAST({{ field }} AS VARCHAR)) > {{ max_length }}
LIMIT 10;
-- 预期：返回 0 条记录 (所有值长度不超过限制)
"""),

    # 6. 枚举值有效性检查
    "enum_value_check": Template("""
-- 测试：验证字段值是否在允许范围内
SELECT
    {{ field }} AS invalid_value,
    COUNT(*) AS cnt
FROM {{ target_table }}
WHERE {{ field }} NOT IN ({{ valid_values }})
  AND {{ field }} IS NOT NULL
GROUP BY {{ field }}
ORDER BY cnt DESC;
-- 预期：返回 0 条记录 (所有值都在枚举范围内)
"""),

    # ==================== 主键/外键检查 ====================
    
    # 7. 主键唯一性检查
    "primary_key_unique": Template("""
-- 测试：验证主键唯一性
SELECT
    {{ pk_field }} AS pk_value,
    COUNT(*) AS duplicate_cnt
FROM {{ target_table }}
GROUP BY {{ pk_field }}
HAVING COUNT(*) > 1
ORDER BY duplicate_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (主键唯一)
"""),

    # 8. 主键非空检查
    "primary_key_not_null": Template("""
-- 测试：验证主键非空
SELECT 
    COUNT(*) AS null_pk_cnt,
    CAST(COUNT(*) AS FLOAT) * 100 / (SELECT COUNT(*) FROM {{ target_table }}) AS null_rate_pct
FROM {{ target_table }}
WHERE {{ pk_field }} IS NULL;
-- 预期：null_pk_cnt = 0 (主键空值率为 0)
"""),

    # 9. 外键参照完整性检查
    "foreign_key_referential_integrity": Template("""
-- 测试：验证外键参照完整性
SELECT
    a.{{ fk_field }} AS orphan_fk_value,
    COUNT(*) AS orphan_cnt
FROM {{ target_table }} a
LEFT JOIN {{ ref_table }} b
    ON a.{{ fk_field }} = b.{{ ref_pk_field }}
WHERE b.{{ ref_pk_field }} IS NULL
  AND a.{{ fk_field }} IS NOT NULL
GROUP BY a.{{ fk_field }}
ORDER BY orphan_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (所有外键都有对应的主键)
"""),

    # ==================== 数据一致性检查 ====================
    
    # 10. 直取字段一致性检查 (一对一)
    "direct_field_consistency": Template("""
-- 测试：验证直取字段与源数据一致
SELECT
    a.{{ target_field }} AS target_value,
    b.{{ source_field }} AS source_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
JOIN {{ source_table }} b
    ON a.{{ join_key }} = b.{{ join_key }}
WHERE a.{{ target_field }} <> b.{{ source_field }}
   OR (a.{{ target_field }} IS NULL AND b.{{ source_field }} IS NOT NULL)
   OR (a.{{ target_field }} IS NOT NULL AND b.{{ source_field }} IS NULL)
GROUP BY a.{{ target_field }}, b.{{ source_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (直取字段值完全一致)
"""),

    # 11. 直取字段一致性检查 (多对一汇总)
    "direct_aggregation_consistency": Template("""
-- 测试：验证汇总数据与源数据一致
SELECT
    a.{{ group_field }},
    SUM(a.{{ target_field }}) AS target_sum,
    SUM(b.{{ source_field }}) AS source_sum,
    ABS(SUM(a.{{ target_field }}) - SUM(b.{{ source_field }})) AS diff,
    CAST(ABS(SUM(a.{{ target_field }}) - SUM(b.{{ source_field }})) AS FLOAT) * 100 / 
        NULLIF(ABS(SUM(b.{{ source_field }})), 0) AS diff_rate_pct
FROM {{ target_table }} a
JOIN {{ source_table }} b
    ON a.{{ join_key }} = b.{{ join_key }}
{% if group_by_condition %}WHERE {{ group_by_condition }}{% endif %}
GROUP BY a.{{ group_field }}
HAVING ABS(SUM(a.{{ target_field }}) - SUM(b.{{ source_field }})) > {{ tolerance | default(0.01) }}
ORDER BY diff DESC
LIMIT 100;
-- 预期：返回 0 条记录 (汇总数据一致，差异在允许范围内)
"""),

    # 12. 计算字段验证检查
    "calculated_field_validation": Template("""
-- 测试：验证计算字段逻辑正确性
SELECT
    {{ target_field }} AS actual_value,
    {{ calculation_expression }} AS expected_value,
    ABS({{ target_field }} - ({{ calculation_expression }})) AS diff
FROM {{ target_table }}
WHERE ABS({{ target_field }} - ({{ calculation_expression }})) > {{ tolerance | default(0.01) }}
LIMIT 100;
-- 预期：返回 0 条记录 (计算字段值与预期一致)
"""),

    # ==================== 度量值检查 ====================
    
    # 13. 度量值汇总准确性检查
    "measure_aggregation_accuracy": Template("""
-- 测试：验证度量值汇总准确性
WITH target_agg AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        SUM({{ measure_field }}) AS target_sum
    FROM {{ target_table }}
    GROUP BY {{ group_fields | join(", ") }}
),
source_agg AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        SUM({{ source_measure }}) AS source_sum
    FROM {{ source_table }}
    {% if source_filter %}WHERE {{ source_filter }}{% endif %}
    GROUP BY {{ group_fields | join(", ") }}
)
SELECT
    a.group_key,
    a.target_sum,
    b.source_sum,
    ABS(a.target_sum - b.source_sum) AS diff,
    CAST(ABS(a.target_sum - b.source_sum) AS FLOAT) * 100 / NULLIF(ABS(b.source_sum), 0) AS diff_rate_pct
FROM target_agg a
JOIN source_agg b ON a.group_key = b.group_key
WHERE ABS(a.target_sum - b.source_sum) > {{ tolerance | default(0.01) }}
ORDER BY diff DESC
LIMIT 100;
-- 预期：返回 0 条记录 (度量值汇总一致)
"""),

    # 14. 度量值非负检查
    "measure_non_negative": Template("""
-- 测试：验证度量值非负 (如适用)
SELECT
    {{ measure_field }} AS negative_value,
    COUNT(*) AS cnt
FROM {{ target_table }}
WHERE {{ measure_field }} < 0
GROUP BY {{ measure_field }}
ORDER BY cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (度量值不应为负)
"""),

    # 15. 度量值极值检查
    "measure_outlier_check": Template("""
-- 测试：验证度量值无异常极值
SELECT
    {{ measure_field }} AS outlier_value,
    COUNT(*) AS cnt
FROM {{ target_table }}
WHERE {{ measure_field }} < {{ min_value }} OR {{ measure_field }} > {{ max_value }}
GROUP BY {{ measure_field }}
ORDER BY cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (度量值在合理范围内)
"""),

    # ==================== 空值检查 ====================
    
    # 16. 字段空值率检查
    "field_null_rate_check": Template("""
-- 测试：验证字段空值率符合要求
SELECT
    COUNT(*) AS total_cnt,
    SUM(CASE WHEN {{ field }} IS NULL THEN 1 ELSE 0 END) AS null_cnt,
    CAST(SUM(CASE WHEN {{ field }} IS NULL THEN 1 ELSE 0 END) AS FLOAT) * 100 / 
        NULLIF(COUNT(*), 0) AS null_rate_pct
FROM {{ target_table }};
-- 预期：null_rate_pct {{ expected_null_rate }}
"""),

    # 17. 必填字段非空检查
    "required_field_not_null": Template("""
-- 测试：验证必填字段非空
SELECT
    {{ field }} AS null_value,
    COUNT(*) AS null_cnt
FROM {{ target_table }}
WHERE {{ field }} IS NULL
GROUP BY {{ field }};
-- 预期：返回 0 条记录 (必填字段不能为空)
"""),

    # ==================== 数据分布检查 ====================
    
    # 18. 数据分布合理性检查
    "data_distribution_check": Template("""
-- 测试：验证数据分布合理性
SELECT
    {{ group_field }} AS group_value,
    COUNT(*) AS cnt,
    CAST(COUNT(*) AS FLOAT) * 100 / SUM(COUNT(*)) OVER() AS pct
FROM {{ target_table }}
GROUP BY {{ group_field }}
ORDER BY cnt DESC;
-- 预期：分布合理，无明显异常集中或缺失
"""),

    # 19. 数据重复性检查
    "data_duplication_check": Template("""
-- 测试：验证数据无异常重复
SELECT
    {{ check_fields | join(", ") }},
    COUNT(*) AS duplicate_cnt
FROM {{ target_table }}
GROUP BY {{ check_fields | join(", ") }}
HAVING COUNT(*) > 1
ORDER BY duplicate_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (无异常重复)
"""),

    # ==================== 复杂规则检查 ====================
    
    # 20. CASE WHEN 规则验证
    "case_when_rule_validation": Template("""
-- 测试：验证 CASE WHEN 规则正确性
SELECT
    {{ target_field }} AS actual_value,
    CASE
        {{ case_when_rules }}
        ELSE {{ else_value }}
    END AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> CASE
        {{ case_when_rules }}
        ELSE {{ else_value }}
    END
GROUP BY {{ target_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (CASE WHEN 规则执行正确)
"""),

    # 21. 多表关联一致性检查
    "multi_join_consistency": Template("""
-- 测试：验证多表关联数据一致性
SELECT
    a.{{ target_field }} AS target_value,
    {{ source_expression }} AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
{% for join_table in join_tables %}
JOIN {{ join_table.table }} {{ join_table.alias }}
    ON {{ join_table.condition }}
{% endfor %}
WHERE a.{{ target_field }} <> {{ source_expression }}
GROUP BY a.{{ target_field }}, {{ source_expression }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录 (多表关联数据一致)
"""),

    # 22. 数据时效性检查
    "data_freshness_check": Template("""
-- 测试：验证数据时效性
SELECT
    MAX({{ time_field }}) AS latest_time,
    MIN({{ time_field }}) AS earliest_time,
    DATEDIFF(hour, MAX({{ time_field }}), GETDATE()) AS hours_since_update
FROM {{ target_table }};
-- 预期：hours_since_update <= {{ max_delay_hours }} (数据更新延迟在允许范围内)
"""),

    # 23. 分区完整性检查
    "partition_completeness": Template("""
-- 测试：验证分区数据完整性
SELECT
    dt AS partition_date,
    COUNT(*) AS row_cnt
FROM {{ target_table }}
WHERE dt >= '{{ start_date }}' AND dt <= '{{ end_date }}'
GROUP BY dt
ORDER BY dt;
-- 预期：每个分区都有数据，无缺失
"""),
}


@dataclass
class SQLGenerationResult:
    """SQL 生成结果"""
    sql: str
    check_type: str
    description: str
    expected_result: str
    params: Dict
    quality_score: float = 0.0  # SQL 质量评分
    warnings: List[str] = None


class SQLGeneratorV2:
    """增强版 SQL 生成器"""

    def __init__(self):
        self.templates = SQL_TEMPLATES
        self._check_type_mapping = self._build_check_type_mapping()

    def _build_check_type_mapping(self) -> Dict[str, str]:
        """构建测试类型到 SQL 模板的映射"""
        return {
            # 表级别检查
            "表存在性检查": "table_exists",
            "表数据量检查": "table_row_count",
            "表主键完整性": "table_primary_key_completeness",
            
            # 字段级别检查
            "字段完整性检查": "field_completeness",
            "字段精度检查": "field_precision_check",
            "枚举值检查": "enum_value_check",
            
            # 主键/外键检查
            "主键唯一性检查": "primary_key_unique",
            "主键非空检查": "primary_key_not_null",
            "外键参照完整性检查": "foreign_key_referential_integrity",
            
            # 数据一致性检查
            "直取字段一致性检查": "direct_field_consistency",
            "汇总数据一致性检查": "direct_aggregation_consistency",
            "计算字段验证检查": "calculated_field_validation",
            
            # 度量值检查
            "度量值汇总准确性检查": "measure_aggregation_accuracy",
            "度量值非负检查": "measure_non_negative",
            "度量值极值检查": "measure_outlier_check",
            
            # 空值检查
            "字段空值率检查": "field_null_rate_check",
            "必填字段非空检查": "required_field_not_null",
            
            # 数据分布检查
            "数据分布合理性检查": "data_distribution_check",
            "数据重复性检查": "data_duplication_check",
            
            # 复杂规则检查
            "CASE WHEN 规则验证": "case_when_rule_validation",
            "多表关联一致性检查": "multi_join_consistency",
            "数据时效性检查": "data_freshness_check",
            "分区完整性检查": "partition_completeness",
        }

    def generate(self, check_type: str, params: Dict) -> SQLGenerationResult:
        """
        生成 SQL 脚本

        Args:
            check_type: 检查类型
            params: 模板参数

        Returns:
            SQLGenerationResult 对象
        """
        if check_type not in self.templates:
            raise ValueError(f"未知的检查类型：{check_type}")

        template = self.templates[check_type]
        
        # 设置默认参数
        default_params = self._get_default_params(check_type)
        default_params.update(params)
        
        # 渲染 SQL
        sql = template.render(**default_params).strip()
        
        # 生成预期结果
        expected_result = self._generate_expected_result(check_type, default_params)
        
        # 质量评分
        quality_score = self._evaluate_sql_quality(sql, check_type)
        
        # 生成警告
        warnings = self._generate_warnings(check_type, default_params)
        
        return SQLGenerationResult(
            sql=sql,
            check_type=check_type,
            description=self._get_check_description(check_type),
            expected_result=expected_result,
            params=default_params,
            quality_score=quality_score,
            warnings=warnings
        )

    def _get_default_params(self, check_type: str) -> Dict:
        """获取默认参数"""
        defaults = {
            "target_schema": "dbo",
            "min_rows": 1,
            "min_partitions": 1,
            "tolerance": 0.01,
            "expected_null_rate": "< 5%",
            "max_delay_hours": 24,
            "valid_values": "'Y', 'N'",
            "group_fields": ["dt"],
            "join_tables": [],
        }
        return defaults

    def _generate_expected_result(self, check_type: str, params: Dict) -> str:
        """生成精确的预期结果"""
        expected_templates = {
            "primary_key_unique": "返回 0 条记录，主键 {pk_field} 唯一性验证通过",
            "primary_key_not_null": "返回 0 条记录，主键 {pk_field} 空值率为 0%",
            "direct_field_consistency": "返回 0 条记录，{target_field} 字段与源数据 {source_field} 完全一致",
            "measure_aggregation_accuracy": "返回 0 条记录，度量值 {measure_field} 汇总差异率 < 0.01%",
            "field_null_rate_check": "null_rate_pct {expected_null_rate}",
            "foreign_key_referential_integrity": "返回 0 条记录，外键 {fk_field} 参照完整性验证通过",
        }
        
        template = expected_templates.get(check_type, "验证通过")
        return template.format(**params)

    def _evaluate_sql_quality(self, sql: str, check_type: str) -> float:
        """
        评估 SQL 质量
        
        评分维度:
        - 完整性 (30%): 是否包含必要的注释和预期结果
        - 准确性 (30%): SQL 语法是否正确
        - 性能 (20%): 是否有性能优化 (如 LIMIT)
        - 可读性 (20%): 格式是否清晰
        """
        score = 0.0
        
        # 完整性检查 (30 分)
        if "-- 测试：" in sql:
            score += 15
        if "-- 预期：" in sql or "-- 预期:" in sql:
            score += 15
        
        # 准确性检查 (30 分) - 简单检查
        sql_upper = sql.upper()
        if "SELECT" in sql_upper:
            score += 15
        if "FROM" in sql_upper:
            score += 15
        
        # 性能检查 (20 分)
        if "LIMIT" in sql_upper or "TOP" in sql_upper:
            score += 20
        
        # 可读性检查 (20 分)
        if sql.count("\n") >= 3:  # 多行格式
            score += 10
        if "AS " in sql_upper:  # 使用别名
            score += 10
        
        return score / 100.0

    def _generate_warnings(self, check_type: str, params: Dict) -> List[str]:
        """生成警告信息"""
        warnings = []
        
        # 检查必要参数
        if "target_table" in params and not params["target_table"]:
            warnings.append("缺少目标表名")
        
        if check_type in ["primary_key_unique", "primary_key_not_null"]:
            if not params.get("pk_field"):
                warnings.append("缺少主键字段名")
        
        if check_type == "direct_field_consistency":
            if not params.get("source_table"):
                warnings.append("缺少源表名")
            if not params.get("join_key"):
                warnings.append("缺少关联键")
        
        return warnings

    def _get_check_description(self, check_type: str) -> str:
        """获取检查描述"""
        descriptions = {
            "table_exists": "验证目标表是否存在",
            "primary_key_unique": "验证主键字段唯一性",
            "primary_key_not_null": "验证主键字段非空",
            "direct_field_consistency": "验证直取字段与源数据一致",
            "measure_aggregation_accuracy": "验证度量值汇总准确性",
            "field_null_rate_check": "验证字段空值率符合要求",
            "foreign_key_referential_integrity": "验证外键参照完整性",
        }
        return descriptions.get(check_type, "数据质量检查")

    def generate_for_test_case(self, test_case: Dict, mapping_info: Dict = None) -> SQLGenerationResult:
        """
        根据测试用例生成 SQL (增强版)

        Args:
            test_case: 测试用例字典
            mapping_info: Mapping 信息 (可选)

        Returns:
            SQLGenerationResult 对象
        """
        case_name = test_case.get("case_name", "")
        
        # 1. 确定检查类型
        check_type = self._match_check_type(case_name)
        
        # 2. 提取参数 (增强版，利用 Mapping 信息)
        params = self._extract_params_enhanced(test_case, mapping_info)
        
        # 3. 生成 SQL
        return self.generate(check_type, params)

    def _match_check_type(self, case_name: str) -> str:
        """匹配检查类型"""
        case_name_upper = case_name.upper()
        
        for name, template in self._check_type_mapping.items():
            if name.upper() in case_name_upper:
                return template
        
        # 默认返回
        return "table_exists"

    def _extract_params_enhanced(self, test_case: Dict, mapping_info: Dict = None) -> Dict:
        """
        增强版参数提取
        
        利用 Mapping 信息提取更准确的参数
        """
        params = {
            "target_table": self._get_first_table(test_case),
            "pk_field": self._extract_pk_field(test_case, mapping_info),
            "source_table": test_case.get("source_table", ""),
            "source_field": test_case.get("source_field", ""),
            "target_field": self._extract_target_field(test_case, mapping_info),
            "join_key": test_case.get("join_key", "id"),
            "measure_field": self._extract_measure_field(test_case, mapping_info),
            "source_measure": test_case.get("source_measure", ""),
            "field": self._extract_field(test_case, mapping_info),
            "condition": test_case.get("condition", ""),
            "tolerance": test_case.get("tolerance", 0.01),
            "expected_null_rate": test_case.get("expected_null_rate", "< 5%"),
            "valid_values": test_case.get("valid_values", ""),
            "ref_table": test_case.get("ref_table", ""),
            "ref_pk_field": test_case.get("ref_pk_field", ""),
            "fk_field": test_case.get("fk_field", ""),
            "group_field": test_case.get("group_field", ""),
            "expected_field_count": test_case.get("expected_field_count", 0),
        }
        
        # 如果有 Mapping 信息，补充更多参数
        if mapping_info:
            params.update(self._extract_params_from_mapping(mapping_info))
        
        return params

    def _extract_params_from_mapping(self, mapping_info: Dict) -> Dict:
        """从 Mapping 信息提取参数"""
        params = {}
        
        # 提取字段精度信息
        if "field_precision" in mapping_info:
            params["max_length"] = mapping_info["field_precision"].get("max_length", 100)
        
        # 提取枚举值
        if "enum_values" in mapping_info:
            params["valid_values"] = ", ".join(f"'{v}'" for v in mapping_info["enum_values"])
        
        # 提取计算表达式
        if "calculation_expression" in mapping_info:
            params["calculation_expression"] = mapping_info["calculation_expression"]
        
        return params

    def _get_first_table(self, test_case: Dict) -> str:
        """获取第一个表名"""
        tables = test_case.get("tables", [])
        if isinstance(tables, list) and len(tables) > 0:
            return tables[0]
        return str(tables) if tables else ""

    def _extract_pk_field(self, test_case: Dict, mapping_info: Dict = None) -> str:
        """提取主键字段"""
        # 优先从 Mapping 信息获取
        if mapping_info and "primary_key" in mapping_info:
            return mapping_info["primary_key"]
        
        # 从测试用例名称推断
        case_name = test_case.get("case_name", "")
        pk_keywords = ["主键", "PRIMARY", "KEY", "ID"]
        for kw in pk_keywords:
            if kw in case_name.upper():
                # 尝试从描述中提取字段名
                desc = test_case.get("description", "")
                if desc:
                    match = re.search(r'(\w+_ID|\w+_KEY)', desc, re.IGNORECASE)
                    if match:
                        return match.group(1)
        
        return "id"  # 默认

    def _extract_target_field(self, test_case: Dict, mapping_info: Dict = None) -> str:
        """提取目标字段"""
        if mapping_info and "target_field" in mapping_info:
            return mapping_info["target_field"]
        
        # 从描述中提取
        desc = test_case.get("description", "")
        match = re.search(r'(\w+\.\w+|\w+)', desc)
        return match.group(1) if match else "field"

    def _extract_measure_field(self, test_case: Dict, mapping_info: Dict = None) -> str:
        """提取度量字段"""
        if mapping_info and "measure_field" in mapping_info:
            return mapping_info["measure_field"]
        
        # 从名称推断
        case_name = test_case.get("case_name", "")
        measure_keywords = ["金额", "AMOUNT", "SUM", "TOTAL", "度量"]
        for kw in measure_keywords:
            if kw in case_name.upper():
                return "amount"
        
        return "amount"

    def _extract_field(self, test_case: Dict, mapping_info: Dict = None) -> str:
        """提取字段名"""
        if mapping_info and "field" in mapping_info:
            return mapping_info["field"]
        
        # 从描述中提取
        desc = test_case.get("description", "")
        match = re.search(r'(\w+)', desc)
        return match.group(1) if match else "field"

    def generate_batch(self, test_cases: List[Dict], mapping_info: Dict = None) -> List[SQLGenerationResult]:
        """
        批量生成 SQL

        Args:
            test_cases: 测试用例列表
            mapping_info: Mapping 信息

        Returns:
            SQLGenerationResult 列表
        """
        results = []
        for test_case in test_cases:
            try:
                result = self.generate_for_test_case(test_case, mapping_info)
                results.append(result)
            except Exception as e:
                results.append(SQLGenerationResult(
                    sql=f"-- 生成失败：{e}",
                    check_type="error",
                    description="SQL 生成失败",
                    expected_result="",
                    params={},
                    quality_score=0.0,
                    warnings=[str(e)]
                ))
        return results

    def get_template_list(self) -> List[Dict]:
        """获取模板列表"""
        return [
            {"name": name, "description": self._get_check_description(name)}
            for name in self.templates.keys()
        ]


# ============== 兼容性别名 ==============
SQLGenerator = SQLGeneratorV2
