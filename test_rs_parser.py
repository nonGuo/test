# -*- coding: utf-8 -*-
"""测试 RS 解析器"""
from core.parser.document_parser import RSParser

# 测试规则匹配
print("=== 测试规则匹配 ===")
parser = RSParser(debug=True)
result = parser.parse('RS样例.docx')

print('\n解析结果:')
print(f'  标题: {result.get("title")}')
print(f'  提取方式: {result.get("extraction_method")}')
print(f'  测试要点: {result.get("test_points")}')

print('\nPrompt 格式:')
print(parser.to_prompt_content(result))