"""
测试 Mapping 解析器与处理器对接
验证"分层提取 + 按需查询"方案
"""
import os
import sys
import json

# 切换到项目目录
os.chdir('D:/Projects/ai/test')
sys.path.insert(0, 'D:/Projects/ai/test')

from core.parser import (
    MappingParser, 
    parse_mapping_file,
    MappingProcessor,
    FieldMetadata,
    RuleSummary,
    DetailedLogic
)


def test_basic_parse():
    """测试基本解析功能"""
    print('=' * 70)
    print('测试 1: 基本解析功能')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    result = parser.parse('mapping样例.xlsx')
    
    print(f'来源表: {result["source_tables"]}')
    print(f'目标表: {result["target_table"]}')
    print(f'表映射数量: {len(result["table_mappings"])}')
    print(f'字段映射数量: {len(result["field_mappings"])}')
    print()


def test_to_processor_format():
    """测试转换为 Processor 格式"""
    print('=' * 70)
    print('测试 2: 转换为 Processor 格式')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    
    processor_data = parser.to_processor_format()
    
    print(f'转换后数据条数: {len(processor_data)}')
    print('\n转换后数据示例:')
    for i, item in enumerate(processor_data[:3]):
        print(f'\n  [{i+1}] {item.get("target_field")}:')
        print(f'      规则类型: {item.get("rule_type")}')
        print(f'      来源: {item.get("source_schema", "")}.{item.get("source_table", "")}.{item.get("source_field", "")}')
        print(f'      转换规则: {item.get("transformation_rule", "")}')
    print()


def test_get_processor():
    """测试一键获取 Processor"""
    print('=' * 70)
    print('测试 3: 一键获取 Processor (核心功能)')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    processor = parser.get_processor()
    
    # 获取元数据摘要
    summary = processor.get_metadata_summary()
    print('元数据摘要:')
    print(f'  总字段数: {summary["total_fields"]}')
    print(f'  主键字段: {summary["primary_keys"]}')
    print(f'  度量字段: {summary["measures"]}')
    print(f'  维度字段: {summary["dimensions"]}')
    print(f'  复杂度分布: {summary["complexity_distribution"]}')
    print(f'  规则类型分布: {summary["rule_type_distribution"]}')
    print()


def test_level1_query():
    """测试 Level 1 元数据查询"""
    print('=' * 70)
    print('测试 4: Level 1 元数据查询')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    processor = parser.get_processor()
    
    # 查询主键字段
    pk_fields = processor.get_level1_metadata({'is_primary_key': True})
    print(f'主键字段 ({len(pk_fields)} 个):')
    for f in pk_fields:
        print(f'  - {f.name} ({f.data_type}), 表: {f.table}')
    
    # 查询度量字段
    measure_fields = processor.get_level1_metadata({'is_measure': True})
    print(f'\n度量字段 ({len(measure_fields)} 个):')
    for f in measure_fields:
        print(f'  - {f.name}, 业务分类: {f.business_category}')
    
    # 查询维度字段
    dim_fields = processor.get_level1_metadata({'is_dimension': True})
    print(f'\n维度字段 ({len(dim_fields)} 个):')
    for f in dim_fields:
        print(f'  - {f.name}, 业务分类: {f.business_category}')
    print()


def test_level2_query():
    """测试 Level 2 规则摘要查询"""
    print('=' * 70)
    print('测试 5: Level 2 规则摘要查询')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    processor = parser.get_processor()
    
    # 获取所有字段
    all_fields = processor.get_level1_metadata()
    
    print('字段规则摘要:')
    for f in all_fields:
        rule = processor.get_level2_summary(f.name)
        if rule:
            print(f'\n  {f.name}:')
            print(f'    规则类型: {rule.rule_type}')
            print(f'    复杂度: {rule.complexity}')
            print(f'    来源: {rule.source_table}.{rule.source_field}')
            print(f'    涉及空值处理: {rule.involves_null_handling}')
    print()


def test_level3_query():
    """测试 Level 3 详细逻辑查询"""
    print('=' * 70)
    print('测试 6: Level 3 详细逻辑查询')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    processor = parser.get_processor()
    
    # 获取有转换规则的字段
    all_fields = processor.get_level1_metadata()
    
    print('字段详细逻辑:')
    for f in all_fields:
        detail = processor.get_level3_detail(f.name)
        if detail and detail.full_expression:
            print(f'\n  {f.name}:')
            print(f'    完整表达式: {detail.full_expression}')
            print(f'    来源表: {detail.source_tables}')
            print(f'    来源字段: {detail.source_fields}')
            if detail.edge_cases:
                print(f'    边界情况: {detail.edge_cases}')
    print()


def test_query_by_test_type():
    """测试按测试类型查询"""
    print('=' * 70)
    print('测试 7: 按测试类型查询 (核心功能)')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    processor = parser.get_processor()
    
    # 主键检查
    pk_info = processor.query_by_test_type('primary_key_check')
    print(f'主键检查测试点:')
    print(f'  相关字段数: {len(pk_info["fields"])}')
    for f in pk_info['fields'][:3]:
        print(f'    - {f["name"]} ({f["data_type"]})')
    
    # 一致性检查
    consistency_info = processor.query_by_test_type('consistency_check')
    print(f'\n一致性检查测试点:')
    print(f'  直接复制字段数: {len(consistency_info["fields"])}')
    for f in consistency_info['fields'][:3]:
        print(f'    - {f["name"]}')
    
    # 空值检查
    null_info = processor.query_by_test_type('null_check')
    print(f'\n空值检查测试点:')
    print(f'  涉及空值处理字段数: {len(null_info["fields"])}')
    for f in null_info['fields'][:3]:
        print(f'    - {f["name"]}')
    print()


def test_rule_type_inference():
    """测试规则类型推断"""
    print('=' * 70)
    print('测试 8: 规则类型推断')
    print('=' * 70)
    
    parser = MappingParser(debug=False)
    
    # 测试各种映射场景
    test_cases = [
        ('直接复制', None, 'DIRECT'),
        ('数据加工', 'nvl(con.contract_key, -999999)', 'FUNC'),  # 含NVL函数
        ('赋值', 'N', 'CONST'),
        ('聚合', 'SUM(amount)', 'AGG'),
        ('条件映射', 'CASE WHEN status = 1 THEN 1 ELSE 0 END', 'CASE'),
        (None, 'a.field1 + b.field2', 'CALC'),
        (None, 'SELECT * FROM other_table', 'SUBQ'),
    ]
    
    print('映射场景 -> 规则类型推断:')
    for scene, rule, expected in test_cases:
        result = parser._infer_rule_type(scene, rule)
        status = '[OK]' if result == expected else '[FAIL]'
        rule_display = rule[:30] if rule else None
        print(f'  {status} 场景="{scene}", 规则="{rule_display}..." -> {result} (预期: {expected})')
    print()


def test_full_workflow():
    """测试完整工作流"""
    print('=' * 70)
    print('测试 9: 完整工作流 (模拟实际使用)')
    print('=' * 70)
    
    # 步骤1: 解析 Mapping 文件
    print('步骤 1: 解析 Mapping 文件...')
    parser = MappingParser(debug=False)
    parser.parse('mapping样例.xlsx')
    print(f'  [OK] 解析完成，共 {len(parser.field_mappings)} 个字段映射')
    
    # 步骤2: 获取 Processor
    print('\n步骤 2: 获取 Processor 实例...')
    processor = parser.get_processor()
    summary = processor.get_metadata_summary()
    print(f'  [OK] Processor 就绪')
    print(f'    - 总字段: {summary["total_fields"]}')
    print(f'    - 主键: {summary["primary_keys"]}')
    print(f'    - 规则类型分布: {summary["rule_type_distribution"]}')
    
    # 步骤3: 模拟生成测试设计时按需查询
    print('\n步骤 3: 模拟测试设计生成 (按需查询)...')
    
    # 3.1 生成主键检查测试点
    print('  3.1 主键检查测试点:')
    pk_info = processor.query_by_test_type('primary_key_check')
    for field in pk_info['fields']:
        print(f'      - 验证 {field["name"]} 唯一性')
        print(f'      - 验证 {field["name"]} 非空')
    
    # 3.2 生成数据一致性测试点
    print('  3.2 数据一致性测试点:')
    consistency_info = processor.query_by_test_type('consistency_check')
    for field in consistency_info['fields']:
        rule = processor.get_level2_summary(field['name'])
        if rule:
            print(f'      - 验证 {field["name"]} 与来源表 {rule.source_table}.{rule.source_field} 一致')
    
    # 3.3 生成 SQL 时获取详细逻辑
    print('  3.3 SQL 生成 (获取 Level 3 详情):')
    for field in pk_info['fields'][:1]:  # 只展示一个
        detail = processor.get_level3_detail(field['name'])
        print(f'      字段: {field["name"]}')
        print(f'      表达式: {detail.full_expression}')
        print(f'      来源表: {detail.source_tables}')
    
    print('\n[OK] 完整工作流测试通过!')
    print()


if __name__ == '__main__':
    test_basic_parse()
    test_to_processor_format()
    test_get_processor()
    test_level1_query()
    test_level2_query()
    test_level3_query()
    test_query_by_test_type()
    test_rule_type_inference()
    test_full_workflow()
    
    print('=' * 70)
    print('所有测试完成!')
    print('=' * 70)