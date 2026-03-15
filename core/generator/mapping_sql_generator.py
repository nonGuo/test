"""
基于 Mapping 规则的 SQL 生成器

根据 Mapping 规则类型自动生成对应的验证 SQL:
- DIRECT (直取): 生成数据一致性检查 SQL
- CALC (计算): 生成计算逻辑验证 SQL
- AGG (聚合): 生成聚合准确性检查 SQL
- CASE (条件): 生成 CASE WHEN 规则验证 SQL
"""
from typing import Dict, List, Optional
from dataclasses import dataclass
from jinja2 import Template


# ============== Mapping 规则专用 SQL 模板 ==============

MAPPING_SQL_TEMPLATES = {
    # ==================== DIRECT 直取规则 ====================
    
    "direct_single_field": Template("""
-- 测试：验证直取字段 {{ target_field }} 与源数据一致
-- 规则类型：DIRECT (直取)
-- 转换规则：{{ transform_rule }}
SELECT
    a.{{ target_field }} AS target_value,
    b.{{ source_field }} AS source_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
INNER JOIN {{ source_table }} b
    ON a.{{ join_key }} = b.{{ join_key }}
WHERE a.{{ target_field }} <> b.{{ source_field }}
   OR (a.{{ target_field }} IS NULL AND b.{{ source_field }} IS NOT NULL)
   OR (a.{{ target_field }} IS NOT NULL AND b.{{ source_field }} IS NULL)
GROUP BY a.{{ target_field }}, b.{{ source_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "direct_with_filter": Template("""
-- 测试：验证带过滤条件的直取字段 {{ target_field }}
-- 规则类型：DIRECT (带过滤)
-- 转换规则：{{ transform_rule }}
SELECT
    a.{{ target_field }} AS target_value,
    b.{{ source_field }} AS source_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
INNER JOIN {{ source_table }} b
    ON a.{{ join_key }} = b.{{ join_key }}
WHERE {{ filter_condition }}
  AND (a.{{ target_field }} <> b.{{ source_field }}
       OR (a.{{ target_field }} IS NULL AND b.{{ source_field }} IS NOT NULL)
       OR (a.{{ target_field }} IS NOT NULL AND b.{{ source_field }} IS NULL))
GROUP BY a.{{ target_field }}, b.{{ source_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== CALC 计算规则 ====================
    
    "calc_basic": Template("""
-- 测试：验证计算字段 {{ target_field }} 逻辑正确性
-- 规则类型：CALC (计算)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    {{ calculation_expression }} AS expected_value,
    ABS({{ target_field }} - ({{ calculation_expression }})) AS diff,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE ABS({{ target_field }} - ({{ calculation_expression }})) > {{ tolerance }}
GROUP BY {{ target_field }}, {{ calculation_expression }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "calc_with_null_handling": Template("""
-- 测试：验证带空值处理的计算字段 {{ target_field }}
-- 规则类型：CALC (含空值处理)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    COALESCE({{ calculation_expression }}, 0) AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> COALESCE({{ calculation_expression }}, 0)
  AND NOT ({{ target_field }} IS NULL AND {{ calculation_expression }} IS NULL)
GROUP BY {{ target_field }}, {{ calculation_expression }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== AGG 聚合规则 ====================
    
    "agg_sum": Template("""
-- 测试：验证 SUM 聚合字段 {{ target_field }} 准确性
-- 规则类型：AGG (SUM)
-- 转换规则：{{ transform_rule }}
WITH target_agg AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        SUM({{ target_field }}) AS target_sum
    FROM {{ target_table }}
    GROUP BY {{ group_fields | join(", ") }}
),
source_agg AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        SUM({{ source_field }}) AS source_sum
    FROM {{ source_table }}
    {% if source_filter %}WHERE {{ source_filter }}{% endif %}
    GROUP BY {{ group_fields | join(", ") }}
)
SELECT
    a.group_key,
    a.target_sum,
    b.source_sum,
    ABS(a.target_sum - b.source_sum) AS diff,
    CAST(ABS(a.target_sum - b.source_sum) AS FLOAT) * 100 / 
        NULLIF(ABS(b.source_sum), 0) AS diff_rate_pct
FROM target_agg a
FULL OUTER JOIN source_agg b ON a.group_key = b.group_key
WHERE ABS(a.target_sum - b.source_sum) > {{ tolerance }}
   OR (a.target_sum IS NULL AND b.source_sum IS NOT NULL)
   OR (a.target_sum IS NOT NULL AND b.source_sum IS NULL)
ORDER BY diff DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "agg_count": Template("""
-- 测试：验证 COUNT 聚合字段 {{ target_field }} 准确性
-- 规则类型：AGG (COUNT)
-- 转换规则：{{ transform_rule }}
WITH target_count AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        COUNT({{ target_field }}) AS target_cnt
    FROM {{ target_table }}
    GROUP BY {{ group_fields | join(", ") }}
),
source_count AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        COUNT({{ source_field }}) AS source_cnt
    FROM {{ source_table }}
    {% if source_filter %}WHERE {{ source_filter }}{% endif %}
    GROUP BY {{ group_fields | join(", ") }}
)
SELECT
    a.group_key,
    a.target_cnt,
    b.source_cnt,
    ABS(a.target_cnt - b.source_cnt) AS diff
FROM target_count a
FULL OUTER JOIN source_count b ON a.group_key = b.group_key
WHERE a.target_cnt <> b.source_cnt
ORDER BY diff DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "agg_avg": Template("""
-- 测试：验证 AVG 聚合字段 {{ target_field }} 准确性
-- 规则类型：AGG (AVG)
-- 转换规则：{{ transform_rule }}
WITH target_avg AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        AVG({{ target_field }}) AS target_avg
    FROM {{ target_table }}
    GROUP BY {{ group_fields | join(", ") }}
),
source_avg AS (
    SELECT 
        {{ group_fields | join(", ") }} AS group_key,
        AVG({{ source_field }}) AS source_avg
    FROM {{ source_table }}
    {% if source_filter %}WHERE {{ source_filter }}{% endif %}
    GROUP BY {{ group_fields | join(", ") }}
)
SELECT
    a.group_key,
    a.target_avg,
    b.source_avg,
    ABS(a.target_avg - b.source_avg) AS diff,
    CAST(ABS(a.target_avg - b.source_avg) AS FLOAT) * 100 / 
        NULLIF(ABS(b.source_avg), 0) AS diff_rate_pct
FROM target_avg a
FULL OUTER JOIN source_avg b ON a.group_key = b.group_key
WHERE ABS(a.target_avg - b.source_avg) > {{ tolerance }}
ORDER BY diff DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== CASE 条件规则 ====================
    
    "case_when_basic": Template("""
-- 测试：验证 CASE WHEN 字段 {{ target_field }} 逻辑正确性
-- 规则类型：CASE (条件)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    CASE
        {{ case_when_clauses }}
    END AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> CASE
        {{ case_when_clauses }}
    END
GROUP BY {{ target_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "case_when_with_else": Template("""
-- 测试：验证 CASE WHEN 字段 {{ target_field }} (含 ELSE) 逻辑正确性
-- 规则类型：CASE (条件)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    CASE
        {{ case_when_clauses }}
        ELSE {{ else_value }}
    END AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> CASE
        {{ case_when_clauses }}
        ELSE {{ else_value }}
    END
GROUP BY {{ target_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== JOIN 关联规则 ====================
    
    "join_single": Template("""
-- 测试：验证单表关联字段 {{ target_field }} 正确性
-- 规则类型：JOIN (关联)
-- 转换规则：{{ transform_rule }}
SELECT
    a.{{ target_field }} AS target_value,
    b.{{ source_field }} AS source_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
INNER JOIN {{ source_table }} b
    ON {{ join_condition }}
WHERE a.{{ target_field }} <> b.{{ source_field }}
GROUP BY a.{{ target_field }}, b.{{ source_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "join_multiple": Template("""
-- 测试：验证多表关联字段 {{ target_field }} 正确性
-- 规则类型：JOIN (多表关联)
-- 转换规则：{{ transform_rule }}
SELECT
    a.{{ target_field }} AS target_value,
    {{ source_expression }} AS source_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
{% for join in joins %}
INNER JOIN {{ join.table }} {{ join.alias }}
    ON {{ join.condition }}
{% endfor %}
WHERE a.{{ target_field }} <> {{ source_expression }}
GROUP BY a.{{ target_field }}, {{ source_expression }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== FUNC 函数规则 ====================
    
    "func_string": Template("""
-- 测试：验证字符串函数字段 {{ target_field }} 正确性
-- 规则类型：FUNC (字符串函数)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    {{ function_expression }} AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> {{ function_expression }}
GROUP BY {{ target_field }}, {{ function_expression }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    "func_date": Template("""
-- 测试：验证日期函数字段 {{ target_field }} 正确性
-- 规则类型：FUNC (日期函数)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    {{ function_expression }} AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> {{ function_expression }}
GROUP BY {{ target_field }}, {{ function_expression }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== CONST 常量规则 ====================
    
    "const_value": Template("""
-- 测试：验证常量字段 {{ target_field }} 值正确性
-- 规则类型：CONST (常量)
-- 转换规则：{{ transform_rule }}
SELECT
    {{ target_field }} AS actual_value,
    '{{ constant_value }}' AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }}
WHERE {{ target_field }} <> '{{ constant_value }}'
GROUP BY {{ target_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),

    # ==================== SUBQ 子查询规则 ====================
    
    "subquery_correlated": Template("""
-- 测试：验证相关子查询字段 {{ target_field }} 正确性
-- 规则类型：SUBQ (子查询)
-- 转换规则：{{ transform_rule }}
SELECT
    a.{{ target_field }} AS actual_value,
    ({{ subquery_template }}) AS expected_value,
    COUNT(*) AS diff_cnt
FROM {{ target_table }} a
WHERE a.{{ target_field }} <> ({{ subquery_template }})
GROUP BY a.{{ target_field }}
ORDER BY diff_cnt DESC
LIMIT 100;
-- 预期：返回 0 条记录
"""),
}


@dataclass
class MappingSQLResult:
    """Mapping SQL 生成结果"""
    sql: str
    rule_type: str
    target_field: str
    source_field: str
    description: str
    expected_result: str
    complexity: str
    params: Dict


class MappingBasedSQLGenerator:
    """基于 Mapping 规则的 SQL 生成器"""

    def __init__(self):
        self.templates = MAPPING_SQL_TEMPLATES

    def generate_from_mapping(self, mapping_rule: Dict) -> MappingSQLResult:
        """
        根据 Mapping 规则生成 SQL

        Args:
            mapping_rule: Mapping 规则字典，包含:
                - target_field: 目标字段
                - source_field: 源字段
                - target_table: 目标表
                - source_table: 源表
                - transform_rule: 转换规则
                - rule_type: 规则类型 (DIRECT/CALC/AGG/CASE/JOIN/FUNC/CONST/SUBQ)
                - join_key: 关联键 (可选)
                - filter_condition: 过滤条件 (可选)

        Returns:
            MappingSQLResult 对象
        """
        rule_type = mapping_rule.get("rule_type", "DIRECT").upper()
        
        # 根据规则类型选择模板
        template_name = self._select_template(rule_type, mapping_rule)
        
        if template_name not in self.templates:
            return self._generate_fallback_sql(mapping_rule)
        
        template = self.templates[template_name]
        
        # 准备参数
        params = self._prepare_params(mapping_rule, rule_type)
        
        # 渲染 SQL
        sql = template.render(**params).strip()
        
        # 生成描述
        description = self._generate_description(rule_type, mapping_rule)
        
        # 生成预期结果
        expected_result = self._generate_expected_result(rule_type, mapping_rule)
        
        # 评估复杂度
        complexity = self._assess_complexity(mapping_rule.get("transform_rule", ""))
        
        return MappingSQLResult(
            sql=sql,
            rule_type=rule_type,
            target_field=mapping_rule.get("target_field", ""),
            source_field=mapping_rule.get("source_field", ""),
            description=description,
            expected_result=expected_result,
            complexity=complexity,
            params=params
        )

    def _select_template(self, rule_type: str, mapping_rule: Dict) -> str:
        """选择模板"""
        transform_rule = mapping_rule.get("transform_rule", "").upper()
        
        if rule_type == "DIRECT":
            if mapping_rule.get("filter_condition"):
                return "direct_with_filter"
            return "direct_single_field"
        
        elif rule_type == "CALC":
            if self._has_null_handling(transform_rule):
                return "calc_with_null_handling"
            return "calc_basic"
        
        elif rule_type == "AGG":
            if "SUM" in transform_rule:
                return "agg_sum"
            elif "COUNT" in transform_rule:
                return "agg_count"
            elif "AVG" in transform_rule:
                return "agg_avg"
            return "agg_sum"  # 默认
        
        elif rule_type == "CASE":
            if "ELSE" in transform_rule:
                return "case_when_with_else"
            return "case_when_basic"
        
        elif rule_type == "JOIN":
            joins = mapping_rule.get("joins", [])
            if len(joins) > 1:
                return "join_multiple"
            return "join_single"
        
        elif rule_type == "FUNC":
            if self._is_date_function(transform_rule):
                return "func_date"
            return "func_string"
        
        elif rule_type == "CONST":
            return "const_value"
        
        elif rule_type == "SUBQ":
            return "subquery_correlated"
        
        return "direct_single_field"

    def _prepare_params(self, mapping_rule: Dict, rule_type: str) -> Dict:
        """准备模板参数"""
        params = {
            "target_field": mapping_rule.get("target_field", ""),
            "source_field": mapping_rule.get("source_field", ""),
            "target_table": mapping_rule.get("target_table", ""),
            "source_table": mapping_rule.get("source_table", ""),
            "transform_rule": mapping_rule.get("transform_rule", ""),
            "join_key": mapping_rule.get("join_key", "id"),
            "tolerance": mapping_rule.get("tolerance", 0.01),
            "group_fields": mapping_rule.get("group_fields", ["dt"]),
            "source_filter": mapping_rule.get("source_filter", ""),
            "filter_condition": mapping_rule.get("filter_condition", ""),
        }
        
        # 计算字段参数
        if rule_type == "CALC":
            params["calculation_expression"] = self._extract_calculation_expression(
                mapping_rule.get("transform_rule", "")
            )
        
        # CASE WHEN 参数
        if rule_type == "CASE":
            case_clauses = self._extract_case_when_clauses(
                mapping_rule.get("transform_rule", "")
            )
            params["case_when_clauses"] = case_clauses
            params["else_value"] = mapping_rule.get("else_value", "NULL")
        
        # 关联参数
        if rule_type == "JOIN":
            params["join_condition"] = mapping_rule.get("join_condition", "")
            params["joins"] = mapping_rule.get("joins", [])
            params["source_expression"] = mapping_rule.get("source_expression", "")
        
        # 常量参数
        if rule_type == "CONST":
            params["constant_value"] = mapping_rule.get("constant_value", "")
        
        # 子查询参数
        if rule_type == "SUBQ":
            params["subquery_template"] = mapping_rule.get("subquery_template", "")
        
        # 函数参数
        if rule_type == "FUNC":
            params["function_expression"] = mapping_rule.get("function_expression", "")
        
        return params

    def _extract_calculation_expression(self, transform_rule: str) -> str:
        """提取计算表达式"""
        # 简单实现：直接使用转换规则
        # 可以进一步优化，解析复杂的表达式
        return transform_rule

    def _extract_case_when_clauses(self, transform_rule: str) -> str:
        """提取 CASE WHEN 子句"""
        # 简单实现：提取 WHEN...THEN 部分
        import re
        matches = re.findall(
            r'WHEN\s+(.+?)\s+THEN\s+(.+?)(?:WHEN|ELSE|END|$)',
            transform_rule,
            re.IGNORECASE
        )
        clauses = []
        for condition, result in matches:
            clauses.append(f"WHEN {condition.strip()} THEN {result.strip()}")
        return "\n        ".join(clauses)

    def _has_null_handling(self, transform_rule: str) -> bool:
        """检查是否有空值处理"""
        keywords = ["COALESCE", "NULLIF", "NVL", "IFNULL", "IS NULL"]
        return any(kw in transform_rule.upper() for kw in keywords)

    def _is_date_function(self, transform_rule: str) -> bool:
        """检查是否是日期函数"""
        keywords = ["DATE", "TIME", "TIMESTAMP", "TO_DATE", "DATE_FORMAT", "TRUNC"]
        return any(kw in transform_rule.upper() for kw in keywords)

    def _assess_complexity(self, transform_rule: str) -> str:
        """评估复杂度"""
        if not transform_rule:
            return "LOW"
        
        score = 0
        
        # CASE WHEN 增加 2 分
        if "CASE" in transform_rule.upper():
            score += 2
        
        # 多表关联增加 2 分
        if transform_rule.upper().count("JOIN") > 1:
            score += 2
        
        # 子查询增加 2 分
        if transform_rule.upper().count("SELECT") > 1:
            score += 2
        
        # 嵌套函数增加 1 分
        if transform_rule.count("(") > 3:
            score += 1
        
        if score <= 1:
            return "LOW"
        elif score <= 3:
            return "MEDIUM"
        else:
            return "HIGH"

    def _generate_description(self, rule_type: str, mapping_rule: Dict) -> str:
        """生成描述"""
        descriptions = {
            "DIRECT": f"验证直取字段 {mapping_rule.get('target_field', '')} 与源数据一致",
            "CALC": f"验证计算字段 {mapping_rule.get('target_field', '')} 逻辑正确性",
            "AGG": f"验证聚合字段 {mapping_rule.get('target_field', '')} 准确性",
            "CASE": f"验证 CASE WHEN 字段 {mapping_rule.get('target_field', '')} 逻辑正确性",
            "JOIN": f"验证关联字段 {mapping_rule.get('target_field', '')} 正确性",
            "FUNC": f"验证函数字段 {mapping_rule.get('target_field', '')} 正确性",
            "CONST": f"验证常量字段 {mapping_rule.get('target_field', '')} 值正确性",
            "SUBQ": f"验证子查询字段 {mapping_rule.get('target_field', '')} 正确性",
        }
        return descriptions.get(rule_type, "数据验证")

    def _generate_expected_result(self, rule_type: str, mapping_rule: Dict) -> str:
        """生成预期结果"""
        target_field = mapping_rule.get("target_field", "")
        return f"返回 0 条记录，{target_field} 字段{rule_type}规则验证通过"

    def _generate_fallback_sql(self, mapping_rule: Dict) -> MappingSQLResult:
        """生成备用 SQL"""
        sql = f"""
-- 测试：验证字段 {mapping_rule.get('target_field', '')}
-- 规则类型：{mapping_rule.get('rule_type', 'UNKNOWN')}
-- 转换规则：{mapping_rule.get('transform_rule', '')}
SELECT COUNT(*) AS cnt
FROM {mapping_rule.get('target_table', '')};
-- 预期：查询成功
"""
        return MappingSQLResult(
            sql=sql.strip(),
            rule_type=mapping_rule.get("rule_type", "UNKNOWN"),
            target_field=mapping_rule.get("target_field", ""),
            source_field=mapping_rule.get("source_field", ""),
            description="数据验证",
            expected_result="查询成功",
            complexity="LOW",
            params={}
        )

    def generate_batch_from_mapping(self, mapping_rules: List[Dict]) -> List[MappingSQLResult]:
        """
        批量生成 SQL

        Args:
            mapping_rules: Mapping 规则列表

        Returns:
            MappingSQLResult 列表
        """
        results = []
        for rule in mapping_rules:
            try:
                result = self.generate_from_mapping(rule)
                results.append(result)
            except Exception as e:
                results.append(self._generate_fallback_sql(rule))
        return results
