"""
SQL 生成器 V2 测试
测试增强的 SQL 生成功能
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.generator.sql_generator_v2 import SQLGeneratorV2, SQLGenerationResult
from core.generator.mapping_sql_generator import MappingBasedSQLGenerator, MappingSQLResult
from core.generator.sql_validator import SQLValidator, SQLOptimizer


def test_sql_generator_v2():
    """测试增强版 SQL 生成器"""
    print("=" * 60)
    print("测试 SQLGeneratorV2")
    print("=" * 60)
    
    generator = SQLGeneratorV2()
    
    # 测试用例 1: 主键唯一性检查
    print("\n[测试 1] 主键唯一性检查")
    result = generator.generate(
        check_type="primary_key_unique",
        params={
            "target_table": "dws_order_f",
            "pk_field": "order_id"
        }
    )
    print(f"SQL:\n{result.sql}")
    print(f"预期结果：{result.expected_result}")
    print(f"质量评分：{result.quality_score * 100:.1f}")
    assert "GROUP BY" in result.sql
    assert "HAVING COUNT(*) > 1" in result.sql
    
    # 测试用例 2: 直取字段一致性检查
    print("\n[测试 2] 直取字段一致性检查")
    result = generator.generate(
        check_type="direct_field_consistency",
        params={
            "target_table": "dws_order_f",
            "source_table": "ods_order",
            "target_field": "order_id",
            "source_field": "order_id",
            "join_key": "order_id"
        }
    )
    print(f"SQL:\n{result.sql}")
    print(f"预期结果：{result.expected_result}")
    assert "JOIN" in result.sql
    assert "WHERE" in result.sql
    
    # 测试用例 3: 度量值汇总准确性检查
    print("\n[测试 3] 度量值汇总准确性检查")
    result = generator.generate(
        check_type="measure_aggregation_accuracy",
        params={
            "target_table": "dws_order_sum_f",
            "source_table": "ods_order",
            "measure_field": "total_amount",
            "source_measure": "amount",
            "group_fields": ["dt", "customer_id"]
        }
    )
    print(f"SQL:\n{result.sql}")
    print(f"预期结果：{result.expected_result}")
    assert "SUM" in result.sql
    assert "WITH" in result.sql  # CTE
    
    # 测试用例 4: CASE WHEN 规则验证
    print("\n[测试 4] CASE WHEN 规则验证")
    result = generator.generate(
        check_type="case_when_rule_validation",
        params={
            "target_table": "dws_order_f",
            "target_field": "order_status",
            "case_when_rules": """
WHEN pay_time IS NOT NULL THEN '已支付'
WHEN cancel_time IS NOT NULL THEN '已取消'
ELSE '待支付'
            """.strip(),
            "else_value": "'待支付'"
        }
    )
    print(f"SQL:\n{result.sql}")
    print(f"预期结果：{result.expected_result}")
    assert "CASE" in result.sql
    assert "WHEN" in result.sql
    
    # 测试用例 5: 基于测试用例生成
    print("\n[测试 5] 基于测试用例生成")
    test_case = {
        "case_name": "验证主键 order_id 唯一性",
        "tables": ["dws_order_f"],
        "description": "验证主键字段 order_id 唯一"
    }
    result = generator.generate_for_test_case(test_case)
    print(f"SQL:\n{result.sql}")
    print(f"检查类型：{result.check_type}")
    print(f"警告：{result.warnings}")
    
    print("\n✅ SQLGeneratorV2 测试通过")


def test_mapping_based_generator():
    """测试基于 Mapping 规则的 SQL 生成器"""
    print("\n" + "=" * 60)
    print("测试 MappingBasedSQLGenerator")
    print("=" * 60)
    
    generator = MappingBasedSQLGenerator()
    
    # 测试用例 1: DIRECT 规则
    print("\n[测试 1] DIRECT 规则 - 直取字段")
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
    print(f"SQL:\n{result.sql}")
    print(f"规则类型：{result.rule_type}")
    print(f"复杂度：{result.complexity}")
    assert "DIRECT" in result.rule_type
    
    # 测试用例 2: CALC 规则
    print("\n[测试 2] CALC 规则 - 计算字段")
    mapping_rule = {
        "target_field": "total_amount",
        "source_field": "",
        "target_table": "dws_order_f",
        "source_table": "",
        "transform_rule": "amount + tax",
        "rule_type": "CALC"
    }
    result = generator.generate_from_mapping(mapping_rule)
    print(f"SQL:\n{result.sql}")
    print(f"规则类型：{result.rule_type}")
    assert "CALC" in result.rule_type
    
    # 测试用例 3: AGG 规则
    print("\n[测试 3] AGG 规则 - SUM 聚合")
    mapping_rule = {
        "target_field": "order_amt_sum",
        "source_field": "order_amt",
        "target_table": "dws_customer_sum_f",
        "source_table": "dws_order_f",
        "transform_rule": "SUM(order_amt)",
        "rule_type": "AGG",
        "group_fields": ["customer_id", "dt"]
    }
    result = generator.generate_from_mapping(mapping_rule)
    print(f"SQL:\n{result.sql}")
    print(f"规则类型：{result.rule_type}")
    print(f"复杂度：{result.complexity}")
    assert "AGG" in result.rule_type
    assert "SUM" in result.sql
    
    # 测试用例 4: CASE 规则
    print("\n[测试 4] CASE 规则 - 条件字段")
    mapping_rule = {
        "target_field": "order_status_name",
        "source_field": "order_status",
        "target_table": "dws_order_f",
        "source_table": "",
        "transform_rule": "CASE WHEN order_status = 1 THEN '待支付' WHEN order_status = 2 THEN '已支付' ELSE '未知' END",
        "rule_type": "CASE"
    }
    result = generator.generate_from_mapping(mapping_rule)
    print(f"SQL:\n{result.sql}")
    print(f"规则类型：{result.rule_type}")
    assert "CASE" in result.rule_type
    assert "WHEN" in result.sql
    
    # 测试用例 5: 批量生成
    print("\n[测试 5] 批量生成")
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
        }
    ]
    results = generator.generate_batch_from_mapping(mapping_rules)
    print(f"生成了 {len(results)} 条 SQL")
    for i, result in enumerate(results, 1):
        print(f"  [{i}] {result.target_field}: {result.rule_type}")
    
    print("\n✅ MappingBasedSQLGenerator 测试通过")


def test_sql_validator():
    """测试 SQL 质量验证器"""
    print("\n" + "=" * 60)
    print("测试 SQLValidator")
    print("=" * 60)
    
    validator = SQLValidator()
    
    # 测试用例 1: 高质量 SQL
    print("\n[测试 1] 高质量 SQL 验证")
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
    print(f"SQL 分数：{result.score:.1f}")
    print(f"是否有效：{result.is_valid}")
    if result.issues:
        print(f"问题：{result.issues}")
    if result.warnings:
        print(f"警告：{result.warnings}")
    if result.suggestions:
        print(f"建议：{result.suggestions}")
    print(f"指标：{result.metrics}")
    assert result.score >= 80
    
    # 测试用例 2: 低质量 SQL
    print("\n[测试 2] 低质量 SQL 验证")
    sql = "SELECT * FROM table WHERE id = 1"
    result = validator.validate(sql)
    print(f"SQL 分数：{result.score:.1f}")
    print(f"是否有效：{result.is_valid}")
    print(f"问题：{result.issues}")
    print(f"警告：{result.warnings}")
    print(f"建议：{result.suggestions}")
    assert result.score < 80
    
    # 测试用例 3: 有问题的 SQL
    print("\n[测试 3] 有语法问题的 SQL")
    sql = """
SELECT order_id, COUNT(
FROM dws_order_f
GROUP BY order_id
"""
    result = validator.validate(sql)
    print(f"SQL 分数：{result.score:.1f}")
    print(f"问题：{result.issues}")
    assert len(result.issues) > 0
    
    # 测试用例 4: 批量验证
    print("\n[测试 4] 批量验证")
    sql_list = [
        "SELECT * FROM t1",
        "SELECT id FROM t2 WHERE id = 1",
        """
        -- 测试
        SELECT id FROM t3
        LIMIT 10;
        -- 预期：成功
        """
    ]
    results = validator.validate_batch(sql_list)
    report = validator.get_validation_report(results)
    print(report)
    
    print("\n✅ SQLValidator 测试通过")


def test_sql_optimizer():
    """测试 SQL 优化器"""
    print("\n" + "=" * 60)
    print("测试 SQLOptimizer")
    print("=" * 60)
    
    optimizer = SQLOptimizer()
    
    # 测试用例 1: 优化 SELECT *
    print("\n[测试 1] 优化 SELECT *")
    sql = "SELECT * FROM users WHERE id = 1"
    optimized = optimizer.optimize(sql)
    print(f"原始：{sql}")
    print(f"优化后：{optimized}")
    
    # 测试用例 2: 优化无 LIMIT 的查询
    print("\n[测试 2] 添加 LIMIT")
    sql = "SELECT id, name FROM users"
    optimized = optimizer.optimize(sql)
    print(f"原始：{sql}")
    print(f"优化后：{optimized}")
    assert "LIMIT" in optimized
    
    print("\n✅ SQLOptimizer 测试通过")


def compare_sql_quality():
    """对比 SQL 质量"""
    print("\n" + "=" * 60)
    print("SQL 质量对比分析")
    print("=" * 60)
    
    validator = SQLValidator()
    generator_v1 = SQLGeneratorV2()  # 使用 V2 作为新版本
    
    # 测试场景
    test_scenarios = [
        {
            "name": "主键唯一性检查",
            "check_type": "primary_key_unique",
            "params": {"target_table": "dws_order_f", "pk_field": "order_id"}
        },
        {
            "name": "直取字段一致性检查",
            "check_type": "direct_field_consistency",
            "params": {
                "target_table": "dws_order_f",
                "source_table": "ods_order",
                "target_field": "order_id",
                "source_field": "order_id",
                "join_key": "order_id"
            }
        },
        {
            "name": "度量值汇总检查",
            "check_type": "measure_aggregation_accuracy",
            "params": {
                "target_table": "dws_sum_f",
                "source_table": "dws_detail_f",
                "measure_field": "amt_sum",
                "source_measure": "amt",
                "group_fields": ["dt"]
            }
        }
    ]
    
    print("\n质量对比结果:")
    print("-" * 60)
    print(f"{'场景':<20} {'分数':<8} {'问题数':<8} {'建议数':<8}")
    print("-" * 60)
    
    for scenario in test_scenarios:
        result = generator_v1.generate(scenario["check_type"], scenario["params"])
        validation = validator.validate(result.sql)
        print(f"{scenario['name']:<20} {validation.score:<8.1f} {len(validation.issues):<8} {len(validation.suggestions):<8}")
    
    print("-" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("SQL 生成器 V2 测试套件")
    print("=" * 60)
    
    test_sql_generator_v2()
    test_mapping_based_generator()
    test_sql_validator()
    test_sql_optimizer()
    compare_sql_quality()
    
    print("\n" + "=" * 60)
    print("✅ 所有测试完成!")
    print("=" * 60)
