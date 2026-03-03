"""
Mapping 元数据处理器
将复杂 Mapping 规则分层提取，支持按需查询

与 MappingParser 配合使用：
    parser = MappingParser()
    parser.parse('mapping.xlsx')
    processor = parser.get_processor()
    
    # 按需查询三层信息
    level1 = processor.get_level1_metadata({'is_primary_key': True})
    level2 = processor.get_level2_summary('field_name')
    level3 = processor.get_level3_detail('field_name')
"""
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


# ============== 数据模型 ==============

@dataclass
class FieldMetadata:
    """Level 1: 字段元数据"""
    name: str                    # 字段名
    table: str                   # 表名
    data_type: str               # 数据类型
    length: int = 0              # 长度
    precision: int = 0           # 精度
    is_primary_key: bool = False # 是否主键
    is_nullable: bool = True     # 是否可空
    is_measure: bool = False     # 是否度量字段
    is_dimension: bool = False   # 是否维度字段
    business_category: str = ""  # 业务分类

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class RuleSummary:
    """Level 2: 规则摘要"""
    target_field: str            # 目标字段
    source_table: str            # 来源表
    source_field: str            # 来源字段
    rule_type: str               # 规则类型
    complexity: str = "LOW"      # 复杂度
    involves_null_handling: bool = False
    involves_case_when: bool = False
    involves_aggregation: bool = False
    involves_join: bool = False
    aggregation_function: str = ""  # SUM/COUNT/AVG...

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DetailedLogic:
    """Level 3: 详细逻辑"""
    target_field: str                    # 目标字段
    full_expression: str                 # 完整 SQL 表达式
    source_tables: List[str] = field(default_factory=list)
    source_fields: List[str] = field(default_factory=list)
    join_conditions: List[str] = field(default_factory=list)
    filter_conditions: List[str] = field(default_factory=list)
    business_rules: List[str] = field(default_factory=list)
    edge_cases: List[str] = field(default_factory=list)
    sample_data: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# ============== 规则类型枚举 ==============

class RuleType:
    DIRECT = "DIRECT"           # 直取
    CALCULATION = "CALC"        # 计算
    AGGREGATION = "AGG"         # 聚合
    JOIN = "JOIN"               # 关联
    CASE_WHEN = "CASE"          # 条件
    CONSTANT = "CONST"          # 常量
    FUNCTION = "FUNC"           # 函数
    SUBQUERY = "SUBQ"           # 子查询


# ============== Mapping 处理器 ==============

class MappingProcessor:
    """Mapping 处理器"""

    def __init__(self):
        self.fields: Dict[str, FieldMetadata] = {}
        self.rules: Dict[str, RuleSummary] = {}
        self.details: Dict[str, DetailedLogic] = {}

    def parse_from_dict(self, mapping_data: List[Dict]) -> None:
        """
        从字典列表解析 Mapping

        Args:
            mapping_data: Mapping 规则列表，支持两种格式：
            
            格式1 (简化格式):
                [
                    {
                        "source_table": "ODS_ORDER",
                        "source_field": "ORDER_ID",
                        "target_table": "DWS_ORDER_SUM",
                        "target_field": "ORDER_ID",
                        "transformation_rule": "ORDER_ID",
                        "rule_type": "DIRECT"
                    }
                ]
            
            格式2 (完整格式，来自 MappingParser.to_processor_format()):
                [
                    {
                        "source_table": "sdi_oder_t",
                        "source_field": "order_id",
                        "target_table": "dwb_cs_order_base_f",
                        "target_field": "order_id",
                        "transformation_rule": "order_id",
                        "rule_type": "DIRECT",
                        "source_schema": "sdiebg",
                        "target_schema": "fin_dwb_cs",
                        "source_field_type": "bigint",
                        "target_field_type": "bigint",
                        "mapping_scene": "直接复制"
                    }
                ]
        """
        for item in mapping_data:
            self._parse_single_rule(item)

    def _parse_single_rule(self, rule: Dict) -> None:
        """解析单条规则"""
        target_field = rule.get("target_field", "")
        
        # 跳过无效记录
        if not target_field:
            return
            
        source_table = rule.get("source_table", "")
        source_field = rule.get("source_field", "")
        target_table = rule.get("target_table", "")
        transformation = rule.get("transformation_rule", "") or rule.get("transform_rule", "")
        rule_type = rule.get("rule_type", RuleType.DIRECT)
        
        # 扩展字段（来自 MappingParser）
        source_schema = rule.get("source_schema", "")
        target_schema = rule.get("target_schema", "")
        target_field_type = rule.get("target_field_type", "")
        source_field_type = rule.get("source_field_type", "")

        # 构建完整表名（含 schema）
        full_target_table = f"{target_schema}.{target_table}" if target_schema and target_table else target_table
        full_source_table = f"{source_schema}.{source_table}" if source_schema and source_table else source_table

        # Level 1: 提取字段元数据
        field_meta = FieldMetadata(
            name=target_field,
            table=full_target_table,
            data_type=self._infer_data_type(transformation, target_field_type),
            is_primary_key=self._is_primary_key(rule_type, target_field),
            is_nullable=self._is_nullable(rule_type),
            is_measure=self._is_measure(rule_type, transformation, target_field),
            is_dimension=self._is_dimension(rule_type, transformation, target_field),
            business_category=self._infer_business_category(target_field)
        )
        self.fields[target_field] = field_meta

        # Level 2: 提取规则摘要
        rule_summary = RuleSummary(
            target_field=target_field,
            source_table=full_source_table,
            source_field=source_field,
            rule_type=rule_type,
            complexity=self._assess_complexity(transformation, rule_type),
            involves_null_handling=self._check_null_handling(transformation),
            involves_case_when=self._check_case_when(transformation),
            involves_aggregation=self._check_aggregation(transformation),
            involves_join=self._check_join(transformation),
            aggregation_function=self._extract_aggregation_func(transformation)
        )
        self.rules[target_field] = rule_summary

        # Level 3: 提取详细逻辑
        detailed_logic = DetailedLogic(
            target_field=target_field,
            full_expression=transformation,
            source_tables=[full_source_table] if full_source_table else [],
            source_fields=[source_field] if source_field else [],
            join_conditions=self._extract_join_conditions(transformation),
            filter_conditions=self._extract_filter_conditions(transformation),
            business_rules=self._extract_business_rules(transformation),
            edge_cases=self._identify_edge_cases(transformation, rule_type)
        )
        self.details[target_field] = detailed_logic

    # ============== 辅助方法 ==============

    def _infer_data_type(self, transformation: str, explicit_type: str = None) -> str:
        """
        推断数据类型
        
        Args:
            transformation: 转换规则
            explicit_type: 显式指定的类型（来自 target_field_type）
        """
        # 优先使用显式指定的类型
        if explicit_type:
            # 简化类型名称（去除长度信息）
            type_upper = explicit_type.upper()
            if '(' in type_upper:
                return type_upper.split('(')[0]
            return type_upper

        if not transformation:
            return "STRING"

        transformation = transformation.upper()
        if "SUM" in transformation or "COUNT" in transformation:
            return "DECIMAL"
        elif "AVG" in transformation:
            return "DECIMAL"
        elif "CAST" in transformation:
            match = re.search(r'CAST\s*\(\s*.*?\s+AS\s+(\w+)', transformation)
            if match:
                return match.group(1)
        elif transformation[0].isdigit():
            return "DECIMAL"
        else:
            return "STRING"

    def _is_primary_key(self, rule_type: str, field_name: str) -> bool:
        """判断是否主键"""
        pk_keywords = ["_ID", "ID_", "CODE", "_NO", "NO_", "_KEY", "KEY_"]
        return any(kw in field_name.upper() for kw in pk_keywords)

    def _is_nullable(self, rule_type: str) -> bool:
        """判断是否可空"""
        if rule_type == RuleType.CONSTANT:
            return False
        return True

    def _is_measure(self, rule_type: str, transformation: str, field_name: str = "") -> bool:
        """判断是否度量字段"""
        if rule_type == RuleType.AGGREGATION:
            return True
        
        # 从字段名判断
        if field_name:
            measure_name_keywords = ["AMT", "AMOUNT", "QTY", "QUANTITY", "PRICE", "CNT", "COUNT", "SUM", "TOTAL"]
            if any(kw in field_name.upper() for kw in measure_name_keywords):
                return True
        
        # 从转换规则判断
        if transformation:
            measure_keywords = ["AMT", "AMOUNT", "QTY", "QUANTITY", "SUM", "COUNT", "PRICE"]
            if any(kw in transformation.upper() for kw in measure_keywords):
                return True
                
        return False

    def _is_dimension(self, rule_type: str, transformation: str, field_name: str = "") -> bool:
        """判断是否维度字段"""
        if self._is_measure(rule_type, transformation, field_name):
            return False
        dim_keywords = ["DATE", "TIME", "TYPE", "STATUS", "CATEGORY", "LEVEL", "FLAG", "IND"]
        if field_name:
            if any(kw in field_name.upper() for kw in dim_keywords):
                return True
        if transformation:
            if any(kw in transformation.upper() for kw in dim_keywords):
                return True
        return False

    def _infer_business_category(self, field_name: str) -> str:
        """推断业务分类"""
        name = field_name.upper()
        if "CUSTOMER" in name or "CLIENT" in name or "USER" in name:
            return "CUSTOMER"
        elif "PRODUCT" in name or "ITEM" in name or "GOODS" in name:
            return "PRODUCT"
        elif "ORDER" in name or "TRADE" in name or "TRANS" in name:
            return "ORDER"
        elif "DATE" in name or "TIME" in name:
            return "TIME"
        elif "AMT" in name or "AMOUNT" in name or "PRICE" in name or "MONEY" in name:
            return "FINANCE"
        elif "CONTRACT" in name:
            return "CONTRACT"
        else:
            return "GENERAL"

    def _assess_complexity(self, transformation: str, rule_type: str) -> str:
        """评估复杂度"""
        if not transformation:
            return "LOW"
            
        if rule_type in [RuleType.DIRECT, RuleType.CONSTANT]:
            return "LOW"

        complexity_score = 0
        
        # CASE WHEN 增加2分
        if "CASE" in transformation.upper() and "WHEN" in transformation.upper():
            complexity_score += 2
        
        # JOIN 增加2分
        if "JOIN" in transformation.upper():
            complexity_score += 2
        
        # 嵌套函数调用
        if transformation.count("(") > 3:
            complexity_score += 1
        
        # 空值处理函数
        if any(kw in transformation.upper() for kw in ["NULLIF", "COALESCE", "NVL", "IFNULL"]):
            complexity_score += 1
        
        # 子查询
        if transformation.upper().count("SELECT") > 1:
            complexity_score += 2
        
        # 多个表关联
        if transformation.upper().count("JOIN") > 1:
            complexity_score += 1

        if complexity_score <= 1:
            return "LOW"
        elif complexity_score <= 3:
            return "MEDIUM"
        else:
            return "HIGH"

    def _check_null_handling(self, transformation: str) -> bool:
        """检查是否涉及空值处理"""
        if not transformation:
            return False
        keywords = ["NULLIF", "COALESCE", "IS NULL", "IS NOT NULL", "NVL", "IFNULL"]
        return any(kw in transformation.upper() for kw in keywords)

    def _check_case_when(self, transformation: str) -> bool:
        """检查是否涉及 CASE WHEN"""
        if not transformation:
            return False
        return "CASE" in transformation.upper() and "WHEN" in transformation.upper()

    def _check_aggregation(self, transformation: str) -> bool:
        """检查是否涉及聚合"""
        if not transformation:
            return False
        keywords = ["SUM(", "COUNT(", "AVG(", "MAX(", "MIN(", 
                   "SUM (", "COUNT (", "AVG (", "MAX (", "MIN ("]
        return any(kw in transformation.upper() for kw in keywords)

    def _check_join(self, transformation: str) -> bool:
        """检查是否涉及关联"""
        if not transformation:
            return False
        return "JOIN" in transformation.upper() or transformation.upper().count("FROM") > 1

    def _extract_aggregation_func(self, transformation: str) -> str:
        """提取聚合函数"""
        if not transformation:
            return ""
        for func in ["SUM", "COUNT", "AVG", "MAX", "MIN"]:
            if f"{func}(" in transformation.upper() or f"{func} (" in transformation.upper():
                return func
        return ""

    def _extract_join_conditions(self, transformation: str) -> List[str]:
        """提取关联条件"""
        if not transformation:
            return []
        conditions = []
        matches = re.findall(
            r'(\w+\.\w+)\s*=\s*(\w+\.\w+)',
            transformation,
            re.IGNORECASE
        )
        for match in matches:
            conditions.append(f"{match[0]} = {match[1]}")
        return conditions

    def _extract_filter_conditions(self, transformation: str) -> List[str]:
        """提取过滤条件"""
        if not transformation:
            return []
        conditions = []
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP BY|ORDER BY|$)',
                               transformation, re.IGNORECASE)
        if where_match:
            conditions.append(where_match.group(1).strip())
        return conditions

    def _extract_business_rules(self, transformation: str) -> List[str]:
        """提取业务规则"""
        if not transformation:
            return []
        rules = []

        # CASE WHEN 规则
        case_matches = re.findall(
            r'WHEN\s+(.+?)\s+THEN\s+(.+?)(?:WHEN|ELSE|END)',
            transformation,
            re.IGNORECASE
        )
        for condition, result in case_matches:
            rules.append(f"当 {condition.strip()} 时，取值 {result.strip()}")

        return rules

    def _identify_edge_cases(self, transformation: str, rule_type: str) -> List[str]:
        """识别边界情况"""
        if not transformation:
            return []
        edge_cases = []

        if self._check_null_handling(transformation):
            edge_cases.append("空值处理")

        if self._check_aggregation(transformation):
            edge_cases.append("零值处理")
            edge_cases.append("全 NULL 情况")

        if self._check_case_when(transformation):
            edge_cases.append("ELSE 分支覆盖")

        return edge_cases

    # ============== 查询方法 ==============

    def get_level1_metadata(self, filter: Dict = None) -> List[FieldMetadata]:
        """获取 Level 1 元数据"""
        fields = list(self.fields.values())

        if not filter:
            return fields

        # 应用过滤
        if filter.get("is_primary_key"):
            fields = [f for f in fields if f.is_primary_key]
        if filter.get("is_measure"):
            fields = [f for f in fields if f.is_measure]
        if filter.get("is_dimension"):
            fields = [f for f in fields if f.is_dimension]
        if filter.get("business_category"):
            fields = [f for f in fields if f.business_category == filter["business_category"]]

        return fields

    def get_level2_summary(self, field_name: str) -> Optional[RuleSummary]:
        """获取字段规则摘要"""
        return self.rules.get(field_name)

    def get_level3_detail(self, field_name: str) -> Optional[DetailedLogic]:
        """获取字段详细逻辑"""
        return self.details.get(field_name)

    def query_by_test_type(self, test_type: str) -> Dict:
        """
        根据测试类型查询相关信息
        
        Args:
            test_type: 测试类型
                - primary_key_check: 主键检查
                - measure_aggregation: 度量聚合检查
                - dimension_check: 维度检查
                - completeness_check: 完整性检查
                - null_check: 空值检查
                - consistency_check: 一致性检查
        """
        if test_type == "primary_key_check":
            fields = self.get_level1_metadata({"is_primary_key": True})
        elif test_type == "measure_aggregation":
            fields = self.get_level1_metadata({"is_measure": True})
        elif test_type == "dimension_check":
            fields = self.get_level1_metadata({"is_dimension": True})
        elif test_type == "null_check":
            # 查找涉及空值处理的字段
            fields = [f for f in self.fields.values() 
                     if f.name in self.rules and self.rules[f.name].involves_null_handling]
        elif test_type == "consistency_check":
            # 查找直接复制的字段
            fields = [f for f in self.fields.values()
                     if f.name in self.rules and self.rules[f.name].rule_type == "DIRECT"]
        else:
            fields = self.get_level1_metadata()

        return {
            "fields": [f.to_dict() for f in fields],
            "rules": [self.rules[f.name].to_dict() for f in fields if f.name in self.rules]
        }

    def get_metadata_summary(self) -> Dict:
        """获取元数据摘要"""
        return {
            "total_fields": len(self.fields),
            "primary_keys": len([f for f in self.fields.values() if f.is_primary_key]),
            "measures": len([f for f in self.fields.values() if f.is_measure]),
            "dimensions": len([f for f in self.fields.values() if f.is_dimension]),
            "complexity_distribution": self._get_complexity_distribution(),
            "rule_type_distribution": self._get_rule_type_distribution()
        }

    def _get_complexity_distribution(self) -> Dict:
        """获取复杂度分布"""
        dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
        for rule in self.rules.values():
            dist[rule.complexity] += 1
        return dist

    def _get_rule_type_distribution(self) -> Dict:
        """获取规则类型分布"""
        dist = {}
        for rule in self.rules.values():
            rule_type = rule.rule_type
            dist[rule_type] = dist.get(rule_type, 0) + 1
        return dist

    def export_to_json(self) -> Dict:
        """导出为 JSON"""
        return {
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "rules": {k: v.to_dict() for k, v in self.rules.items()},
            "details": {k: v.to_dict() for k, v in self.details.items()}
        }
