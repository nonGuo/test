# -*- coding: utf-8 -*-
"""测试应用启动"""
from api.app import create_app

if __name__ == '__main__':
    print("正在创建应用...")
    app = create_app()
    print("应用创建成功！")
    
    # 测试导入核心模块
    print("\n正在测试核心模块导入...")
    from core.ai import LLMClientFactory
    from core.parser.document_parser import RSParser, TSParser
    from core.parser.mapping_parser import MappingParser
    from core.analyzer import DesignGenerator
    from core.generator import XMindGenerator
    print("所有核心模块导入成功！")
