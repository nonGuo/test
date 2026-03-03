"""
SQL 测试脚本生成器
根据测试用例类型生成标准 SQL 脚本
"""
from typing import Dict, List, Optional
from jinja2 import Template


# ============== SQL 模板 ==============

SQL_TEMPLATES = {
    # 表存在性检查
    "table_exists": Template("""
SELECT COUNT(*) AS cnt 
FROM {{ target_table }};
-- 预期：查询成功，cnt >= 0
"""),
    
    # 字段完整性检查
    "field_completeness": Template("""
SELECT 
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    NUMERIC_PRECISION,
    NUMERIC_SCALE
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = '{{ target_table }}'
ORDER BY ORDINAL_POSITION;
-- 预期：字段数量={{ expected_count }}, 各字段属性与 Mapping 一致
"""),
    
    # 主键唯一性检查
    "primary_key_unique": Template("""
SELECT 
    {{ pk_field }} AS pk_value,
    COUNT(*) AS cnt
FROM {{ target_table }}
GROUP BY {{ pk_field }}
HAVING COUNT(*) > 1;
-- 预期：返回 0 条记录
"""),
    
    # 主键非空检查
    "primary_key_not_null": Template("""
SELECT COUNT(*) AS null_cnt
FROM {{ target_table }}
WHERE {{ pk_field }} IS NULL;
-- 预期：返回 0 条记录
"""),
    
    # 直取字段一致性检查
    "direct_field_consistency": Template("""
SELECT 
    a.{{ target_field }},
    b.{{ source_field }}
FROM {{ target_table }} a
JOIN {{ source_table }} b 
    ON a.{{ join_key }} = b.{{ join_key }}
{% if condition %}WHERE {{ condition }}{% endif %}
EXCEPT
SELECT 
    a.{{ target_field }},
    b.{{ source_field }}
FROM {{ target_table }} a
JOIN {{ source_table }} b 
    ON a.{{ join_key }} = b.{{ join_key }}
WHERE a.{{ target_field }} = b.{{ source_field }};
-- 预期：返回 0 条记录
"""),
    
    # 度量值汇总准确性检查
    "measure_aggregation": Template("""
SELECT 
    SUM(a.{{ measure_field }}) AS target_sum,
    b.source_sum,
    ABS(SUM(a.{{ measure_field }}) - b.source_sum) AS diff
FROM {{ target_table }} a
CROSS JOIN (
    SELECT SUM({{ source_measure }}) AS source_sum
    FROM {{ source_table }}
    {% if condition %}WHERE {{ condition }}{% endif %}
) b;
-- 预期：diff = 0 或 diff < {{ threshold }}
"""),
    
    # 空值率检查
    "null_rate_check": Template("""
SELECT 
    COUNT(*) AS total_cnt,
    SUM(CASE WHEN {{ field }} IS NULL THEN 1 ELSE 0 END) AS null_cnt,
    CAST(SUM(CASE WHEN {{ field }} IS NULL THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) AS null_rate
FROM {{ target_table }};
-- 预期：null_rate {{ expected_rate }}
"""),
    
    # 数据有效性检查 (枚举值)
    "valid_value_check": Template("""
SELECT 
    {{ field }} AS invalid_value,
    COUNT(*) AS cnt
FROM {{ target_table }}
WHERE {{ field }} NOT IN ({{ valid_values }})
GROUP BY {{ field }};
-- 预期：返回 0 条记录
"""),
    
    # 参照完整性检查
    "referential_integrity": Template("""
SELECT 
    a.{{ fk_field }} AS fk_value,
    COUNT(*) AS cnt
FROM {{ target_table }} a
LEFT JOIN {{ ref_table }} b 
    ON a.{{ fk_field }} = b.{{ ref_pk_field }}
WHERE b.{{ ref_pk_field }} IS NULL
  AND a.{{ fk_field }} IS NOT NULL
GROUP BY a.{{ fk_field }};
-- 预期：返回 0 条记录
"""),
    
    # 数据分布检查
    "data_distribution": Template("""
SELECT 
    {{ group_field }},
    COUNT(*) AS cnt,
    CAST(COUNT(*) AS FLOAT) / SUM(COUNT(*)) OVER() AS pct
FROM {{ target_table }}
GROUP BY {{ group_field }}
ORDER BY cnt DESC;
-- 预期：分布合理，无明显异常
"""),
}


class SQLGenerator:
    """SQL 脚本生成器"""
    
    def __init__(self):
        self.templates = SQL_TEMPLATES
    
    def generate(self, check_type: str, params: Dict) -> str:
        """
        生成 SQL 脚本
        
        Args:
            check_type: 检查类型
            params: 模板参数
            
        Returns:
            SQL 脚本
        """
        if check_type not in self.templates:
            raise ValueError(f"未知的检查类型：{check_type}")
        
        template = self.templates[check_type]
        return template.render(**params).strip()
    
    def generate_for_test_case(self, test_case: Dict) -> str:
        """
        根据测试用例生成 SQL
        
        Args:
            test_case: 测试用例字典
            
        Returns:
            SQL 脚本
        """
        check_type_map = {
            "表存在性检查": "table_exists",
            "字段完整性检查": "field_completeness",
            "主键唯一性检查": "primary_key_unique",
            "主键非空检查": "primary_key_not_null",
            "数据一致性检查": "direct_field_consistency",
            "度量值准确性检查": "measure_aggregation",
            "空值率检查": "null_rate_check",
            "数据有效性检查": "valid_value_check",
            "参照完整性检查": "referential_integrity",
        }
        
        case_name = test_case.get("case_name", "")
        check_type = None
        
        for name, ctype in check_type_map.items():
            if name in case_name:
                check_type = ctype
                break
        
        if not check_type:
            check_type = "table_exists"  # 默认
        
        # 提取参数
        params = {
            "target_table": test_case.get("tables", [""])[0] if test_case.get("tables") else "",
            "pk_field": self._extract_field(test_case),
            "source_table": test_case.get("source_table", ""),
            "source_field": test_case.get("source_field", ""),
            "target_field": test_case.get("target_field", ""),
            "join_key": test_case.get("join_key", "id"),
            "measure_field": test_case.get("measure_field", ""),
            "source_measure": test_case.get("source_measure", ""),
            "field": self._extract_field(test_case),
            "condition": test_case.get("condition", ""),
            "threshold": test_case.get("threshold", "0.01"),
            "expected_rate": test_case.get("expected_rate", "< 0.1"),
            "valid_values": test_case.get("valid_values", ""),
            "ref_table": test_case.get("ref_table", ""),
            "ref_pk_field": test_case.get("ref_pk_field", ""),
            "fk_field": test_case.get("fk_field", ""),
            "group_field": test_case.get("group_field", ""),
            "expected_count": test_case.get("expected_count", 0),
        }
        
        return self.generate(check_type, params)
    
    def _extract_field(self, test_case: Dict) -> str:
        """从测试用例中提取字段名"""
        # 简单实现，可根据实际情况优化
        title = test_case.get("case_name", "")
        if "主键" in title:
            return "id"
        return "field_name"


class SQLTemplateManager:
    """SQL 模板管理器"""
    
    def __init__(self, template_dir: str):
        """
        初始化模板管理器
        
        Args:
            template_dir: 模板文件目录
        """
        self.template_dir = template_dir
        self.custom_templates = {}
        self._load_custom_templates()
    
    def _load_custom_templates(self):
        """加载自定义模板"""
        import os
        from jinja2 import Environment, FileSystemLoader
        
        if os.path.exists(self.template_dir):
            env = Environment(loader=FileSystemLoader(self.template_dir))
            for name in env.list_templates():
                self.custom_templates[name] = env.get_template(name)
    
    def get_template(self, name: str) -> Optional[Template]:
        """获取模板"""
        return self.custom_templates.get(name)
    
    def add_template(self, name: str, template_str: str) -> None:
        """添加自定义模板"""
        self.custom_templates[name] = Template(template_str)
