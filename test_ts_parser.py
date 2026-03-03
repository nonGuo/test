# -*- coding: utf-8 -*-
"""测试 TS 解析器"""
from core.parser.document_parser import TSParser, DWSTableMetadata

# 测试 DWSTableMetadata
print('=== 测试 DWSTableMetadata ===')
table = DWSTableMetadata()
table.table_name = 'dws_order_i'
table.table_type = 'INTERFACE'
table.is_view = True
table.underlying_f_table = 'dws_order_f'
table.source_tables = ['ods_order', 'dim_customer']
table.primary_keys = ['order_id']

print(f'表名: {table.table_name}')
print(f'表类型: {table.table_type}')
print(f'测试目标表: {table.get_test_target_table()}')
print(f'分布检查表: {table.get_distribution_check_table()}')

# 测试 to_dict
print(f'\nto_dict: {table.to_dict()}')

# 测试 TSParser 初始化
print('\n=== 测试 TSParser ===')
parser = TSParser(debug=True)
print('TSParser 初始化成功')

# 测试 to_prompt_content (不调用 LLM)
result = {
    'interface_table': table,
    'fact_table': None,
    'temp_tables': []
}
print('\nto_prompt_content:')
print(parser.to_prompt_content(result))