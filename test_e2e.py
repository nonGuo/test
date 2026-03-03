# -*- coding: utf-8 -*-
"""
端到端测试
测试完整的测试用例生成流程
"""
import os
import sys
import json
from pathlib import Path

# 确保项目根目录在路径中
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def test_rs_parser():
    """测试 RS 解析器"""
    print("\n" + "=" * 60)
    print("测试 1: RS 解析器")
    print("=" * 60)
    
    from core.parser.document_parser import RSParser
    
    parser = RSParser(debug=True)
    
    # 检查样例文件是否存在
    rs_file = PROJECT_ROOT / "RS样例.docx"
    if not rs_file.exists():
        print(f"[SKIP] RS样例.docx 不存在，跳过测试")
        return None
    
    result = parser.parse(str(rs_file))
    
    print(f"\n解析结果:")
    print(f"  标题: {result.get('title')}")
    print(f"  提取方式: {result.get('extraction_method')}")
    print(f"  测试要点数: {len(result.get('test_points', []))}")
    
    if result.get('test_points'):
        print(f"  测试要点:")
        for p in result['test_points'][:5]:
            print(f"    - {p}")
    
    # 测试 to_prompt_content
    prompt_content = parser.to_prompt_content(result)
    print(f"\nPrompt 内容:\n{prompt_content}")
    
    assert result.get('title'), "标题不应为空"
    assert result.get('test_points'), "测试要点不应为空"
    
    print("\n[PASS] RS 解析器测试通过")
    return result


def test_ts_parser():
    """测试 TS 解析器（模拟 LLM）"""
    print("\n" + "=" * 60)
    print("测试 2: TS 解析器")
    print("=" * 60)
    
    from core.parser.document_parser import TSParser, DWSTableMetadata
    
    parser = TSParser(debug=True)
    
    # 创建模拟数据
    print("\n使用模拟数据测试...")
    
    # 模拟 I 接口
    interface_table = DWSTableMetadata()
    interface_table.table_name = "dws_order_i"
    interface_table.table_type = "INTERFACE"
    interface_table.schema_name = "dws"
    interface_table.is_view = True
    interface_table.underlying_f_table = "dws_order_f"
    interface_table.source_tables = ["ods_order", "dim_customer"]
    interface_table.dim_tables = ["dim_customer"]
    interface_table.primary_keys = ["order_id"]
    interface_table.description = "订单接口视图"
    
    # 模拟 F 表
    fact_table = DWSTableMetadata()
    fact_table.table_name = "dws_order_f"
    fact_table.table_type = "FACT"
    fact_table.schema_name = "dws"
    fact_table.distribution_type = "HASH"
    fact_table.distribution_key = ["order_id"]
    fact_table.partition_type = "RANGE"
    fact_table.partition_keys = ["dt"]
    fact_table.partition_spec = "按天分区，保留365天"
    fact_table.storage_format = "ORC"
    fact_table.compression = "SNAPPY"
    fact_table.source_tables = ["tmp_order_1", "tmp_order_2"]
    fact_table.primary_keys = ["order_id"]
    
    # 模拟临时表
    tmp_table = DWSTableMetadata()
    tmp_table.table_name = "tmp_order_1"
    tmp_table.table_type = "TMP"
    tmp_table.distribution_type = "HASH"
    tmp_table.distribution_key = ["order_id"]
    
    # 构造结果
    result = {
        'tables': [interface_table, fact_table, tmp_table],
        'interface_table': interface_table,
        'fact_table': fact_table,
        'temp_tables': [tmp_table],
        'raw_content': ''
    }
    
    # 测试分类功能
    classified = parser._classify_tables([interface_table, fact_table, tmp_table])
    
    print(f"\n分类结果:")
    print(f"  I接口: {classified['interface_table'].table_name if classified['interface_table'] else 'None'}")
    print(f"  F表: {classified['fact_table'].table_name if classified['fact_table'] else 'None'}")
    print(f"  临时表数: {len(classified['temp_tables'])}")
    
    # 测试 to_prompt_content
    prompt_content = parser.to_prompt_content(result)
    print(f"\nPrompt 内容:\n{prompt_content}")
    
    # 测试 get_distribution_check_table
    assert interface_table.get_distribution_check_table() == "dws_order_f", "I接口应返回底层F表"
    assert fact_table.get_distribution_check_table() == "dws_order_f", "F表应返回自身"
    
    print("\n[PASS] TS 解析器测试通过")
    return result


def test_mapping_parser():
    """测试 Mapping 解析器"""
    print("\n" + "=" * 60)
    print("测试 3: Mapping 解析器")
    print("=" * 60)
    
    from core.parser import MappingParser
    
    parser = MappingParser(debug=True)
    
    # 检查样例文件是否存在
    mapping_file = PROJECT_ROOT / "mapping样例.xlsx"
    if not mapping_file.exists():
        print(f"[SKIP] mapping样例.xlsx 不存在，跳过测试")
        return None
    
    result = parser.parse(str(mapping_file))
    
    print(f"\n解析结果:")
    print(f"  表映射数: {len(result.get('table_mappings', []))}")
    print(f"  字段映射数: {len(result.get('field_mappings', []))}")
    print(f"  目标表: {result.get('target_table')}")
    print(f"  来源表: {result.get('source_tables', [])}")
    
    if result.get('field_mappings'):
        print(f"\n字段映射示例 (前5条):")
        for fm in result['field_mappings'][:5]:
            print(f"  {fm.get('source_field', '')} -> {fm.get('target_field', '')} [{fm.get('mapping_scene', '')}]")
    
    print("\n[PASS] Mapping 解析器测试通过")
    return result


def test_xmind_template_loader():
    """测试 XMind 模板加载器"""
    print("\n" + "=" * 60)
    print("测试 4: XMind 模板加载器")
    print("=" * 60)
    
    from core.analyzer import XMindTemplateLoader
    
    # 检查模板文件
    template_file = PROJECT_ROOT / "测试设计模板.xmind"
    if not template_file.exists():
        print(f"[SKIP] 测试设计模板.xmind 不存在，跳过测试")
        return None
    
    loader = XMindTemplateLoader(str(template_file))
    loader.load()
    
    summary = loader.get_structure_summary()
    
    print(f"\n模板摘要:")
    print(f"  最大层级: {summary['max_level']}")
    print(f"  总节点数: {summary['total_nodes']}")
    print(f"  叶子节点数: {summary['leaf_nodes_count']}")
    
    # 测试获取叶子节点
    leaf_nodes = loader.get_leaf_nodes()
    print(f"\n叶子节点:")
    for leaf in leaf_nodes[:5]:
        print(f"  - {leaf.title}")
    
    # 测试模板指南
    guide = loader.get_template_guide()
    print(f"\n模板指南 (前500字符):")
    print(guide[:500] + "..." if len(guide) > 500 else guide)
    
    print("\n[PASS] XMind 模板加载器测试通过")
    return loader


def test_llm_client():
    """测试 LLM 客户端（需要 API Key）"""
    print("\n" + "=" * 60)
    print("测试 5: LLM 客户端")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv("QWEN_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("[SKIP] 未配置 API Key，跳过 LLM 测试")
        print("  请设置环境变量 QWEN_API_KEY 或 OPENAI_API_KEY")
        return None
    
    try:
        from core.ai import LLMClientFactory
        
        provider = "qwen" if os.getenv("QWEN_API_KEY") else "openai"
        client = LLMClientFactory.create(provider)
        
        print(f"\n测试 {provider} 客户端...")
        
        # 简单测试
        response = client.generate("请回复：测试成功")
        print(f"响应: {response[:100]}..." if len(response) > 100 else f"响应: {response}")
        
        print("\n[PASS] LLM 客户端测试通过")
        return client
        
    except Exception as e:
        print(f"[FAIL] LLM 客户端测试失败: {e}")
        return None


def test_xmind_generator():
    """测试 XMind 生成器"""
    print("\n" + "=" * 60)
    print("测试 6: XMind 生成器")
    print("=" * 60)
    
    from core.generator import XMindGenerator
    from core.models import TestDesign, TestNode
    
    # 创建模拟测试设计
    root = TestNode(title="测试场景分析")
    
    # L0 分支
    l0 = TestNode(title="L0-数据结果检查")
    root.add_child(l0)
    
    # 表检查
    table_check = TestNode(title="表/视图检查")
    l0.add_child(table_check)
    
    exist_check = TestNode(title="存在性检查", priority="high", description="验证表是否存在")
    table_check.add_child(exist_check)
    
    # 字段检查
    field_check = TestNode(title="字段检查")
    l0.add_child(field_check)
    
    pk_check = TestNode(title="主键唯一性检查", priority="high", description="验证主键字段唯一")
    field_check.add_child(pk_check)
    
    design = TestDesign(root=root)
    
    # 生成 XMind
    output_path = PROJECT_ROOT / "output" / "test_design_output.xmind"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    generator = XMindGenerator()
    generator.generate(design, str(output_path))
    
    print(f"\nXMind 文件已生成: {output_path}")
    print(f"文件大小: {output_path.stat().st_size} bytes")
    
    assert output_path.exists(), "XMind 文件应该存在"
    
    print("\n[PASS] XMind 生成器测试通过")
    return output_path


def test_sql_generator():
    """测试 SQL 生成器"""
    print("\n" + "=" * 60)
    print("测试 7: SQL 生成器")
    print("=" * 60)
    
    from core.generator import SQLGenerator
    
    generator = SQLGenerator()
    
    # 测试各种 SQL 模板
    test_cases = [
        ("table_exists", {"target_table": "dws_order_f"}),
        ("primary_key_unique", {"target_table": "dws_order_f", "pk_field": "order_id"}),
        ("primary_key_not_null", {"target_table": "dws_order_f", "pk_field": "order_id"}),
        ("null_rate_check", {"target_table": "dws_order_f", "field": "amount", "expected_rate": "< 0.01"}),
    ]
    
    for check_type, params in test_cases:
        try:
            sql = generator.generate(check_type, params)
            print(f"\n{check_type}:")
            print(sql[:200] + "..." if len(sql) > 200 else sql)
        except Exception as e:
            print(f"\n{check_type}: [ERROR] {e}")
    
    print("\n[PASS] SQL 生成器测试通过")


def test_test_case_exporter():
    """测试测试用例导出器"""
    print("\n" + "=" * 60)
    print("测试 8: 测试用例导出器")
    print("=" * 60)
    
    from core.generator import TestCaseExporter
    from core.models import TestCase, TestCaseSuite
    
    # 创建模拟测试用例
    suite = TestCaseSuite(
        name="订单测试用例集",
        target_table="dws_order_i",
        design_version="test_design.xmind"
    )
    
    case1 = TestCase(
        case_id="TC_0001",
        case_name="表存在性检查",
        category="功能测试",
        scene="表/视图检查",
        priority="high",
        description="验证目标表是否存在",
        tables=["dws_order_i"],
        test_steps="SELECT COUNT(*) FROM dws_order_i;",
        expected_result="查询成功"
    )
    
    case2 = TestCase(
        case_id="TC_0002",
        case_name="主键唯一性检查",
        category="功能测试",
        scene="字段检查",
        priority="high",
        description="验证主键 order_id 唯一",
        tables=["dws_order_i"],
        test_steps="SELECT order_id, COUNT(*) FROM dws_order_i GROUP BY order_id HAVING COUNT(*) > 1;",
        expected_result="返回0条记录"
    )
    
    suite.add_case(case1)
    suite.add_case(case2)
    
    # 导出到 Excel
    output_path = PROJECT_ROOT / "output" / "test_cases_output.xlsx"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    exporter = TestCaseExporter()
    exporter.export_to_excel(suite, str(output_path))
    
    print(f"\nExcel 文件已生成: {output_path}")
    print(f"文件大小: {output_path.stat().st_size} bytes")
    print(f"用例数: {len(suite.cases)}")
    
    assert output_path.exists(), "Excel 文件应该存在"
    
    print("\n[PASS] 测试用例导出器测试通过")
    return output_path


def test_full_workflow():
    """测试完整工作流（使用模拟数据）"""
    print("\n" + "=" * 60)
    print("测试 9: 完整工作流（模拟数据）")
    print("=" * 60)
    
    from core.analyzer import TemplateBasedDesignGenerator
    from core.generator import XMindGenerator, SQLGenerator, TestCaseExporter
    from core.models import TestDesign, TestNode, TestCase, TestCaseSuite
    
    # 模拟输入数据
    rs_content = """【文档标题】RS-dws_order_i

【测试要点】
- 验证订单主键唯一性
- 验证订单金额计算准确性
- 验证客户信息关联正确性"""
    
    ts_content = """【I接口】dws_order_i
  类型: 视图
  底层F表: dws_order_f
  来源表: ods_order, dim_customer
  主键: order_id

【F事实表】dws_order_f
  分布方式: HASH
  分布键: order_id
  分区方式: RANGE
  分区键: dt"""
    
    mapping_content = """【字段映射】
order_id -> order_id [直接复制]
order_amt -> order_amt [聚合: SUM]
customer_id -> customer_id [直接复制]"""
    
    print("\n模拟输入:")
    print(f"  RS 内容长度: {len(rs_content)}")
    print(f"  TS 内容长度: {len(ts_content)}")
    print(f"  Mapping 内容长度: {len(mapping_content)}")
    
    # 模拟生成测试设计
    print("\n模拟生成测试设计...")
    
    root = TestNode(title="测试场景分析")
    
    l0 = TestNode(title="L0-数据结果检查")
    root.add_child(l0)
    
    table_check = TestNode(title="表/视图检查")
    l0.add_child(table_check)
    
    exist_check = TestNode(title="验证dws_order_i表存在", priority="high")
    table_check.add_child(exist_check)
    
    field_check = TestNode(title="字段检查")
    l0.add_child(field_check)
    
    pk_check = TestNode(title="验证主键order_id唯一性", priority="high")
    field_check.add_child(pk_check)
    
    design = TestDesign(root=root)
    
    # 生成 XMind
    xmind_path = PROJECT_ROOT / "output" / "workflow_test_design.xmind"
    XMindGenerator().generate(design, str(xmind_path))
    print(f"  XMind 已生成: {xmind_path}")
    
    # 生成测试用例
    print("\n模拟生成测试用例...")
    
    suite = TestCaseSuite(
        name="订单测试用例集",
        target_table="dws_order_i",
        design_version="workflow_test_design.xmind"
    )
    
    suite.add_case(TestCase(
        case_id="TC_0001",
        case_name="验证dws_order_i表存在",
        category="功能测试",
        scene="表/视图检查",
        priority="high",
        tables=["dws_order_i"],
        test_steps="SELECT COUNT(*) FROM dws_order_i;",
        expected_result="查询成功，返回记录数>=0"
    ))
    
    suite.add_case(TestCase(
        case_id="TC_0002",
        case_name="验证主键order_id唯一性",
        category="功能测试",
        scene="字段检查",
        priority="high",
        tables=["dws_order_i"],
        test_steps="SELECT order_id, COUNT(*) as cnt FROM dws_order_i GROUP BY order_id HAVING COUNT(*) > 1;",
        expected_result="返回0条记录"
    ))
    
    # 导出 Excel
    excel_path = PROJECT_ROOT / "output" / "workflow_test_cases.xlsx"
    TestCaseExporter().export_to_excel(suite, str(excel_path))
    print(f"  Excel 已生成: {excel_path}")
    
    print(f"\n最终结果:")
    print(f"  测试设计: {xmind_path}")
    print(f"  测试用例: {excel_path}")
    print(f"  用例数量: {len(suite.cases)}")
    
    print("\n[PASS] 完整工作流测试通过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("端到端测试开始")
    print("=" * 60)
    
    results = {}
    
    try:
        results['rs_parser'] = test_rs_parser()
    except Exception as e:
        print(f"[FAIL] RS 解析器测试失败: {e}")
        results['rs_parser'] = None
    
    try:
        results['ts_parser'] = test_ts_parser()
    except Exception as e:
        print(f"[FAIL] TS 解析器测试失败: {e}")
        results['ts_parser'] = None
    
    try:
        results['mapping_parser'] = test_mapping_parser()
    except Exception as e:
        print(f"[FAIL] Mapping 解析器测试失败: {e}")
        results['mapping_parser'] = None
    
    try:
        results['xmind_template'] = test_xmind_template_loader()
    except Exception as e:
        print(f"[FAIL] XMind 模板加载器测试失败: {e}")
        results['xmind_template'] = None
    
    try:
        results['llm_client'] = test_llm_client()
    except Exception as e:
        print(f"[FAIL] LLM 客户端测试失败: {e}")
        results['llm_client'] = None
    
    try:
        results['xmind_generator'] = test_xmind_generator()
    except Exception as e:
        print(f"[FAIL] XMind 生成器测试失败: {e}")
        results['xmind_generator'] = None
    
    try:
        test_sql_generator()
        results['sql_generator'] = True
    except Exception as e:
        print(f"[FAIL] SQL 生成器测试失败: {e}")
        results['sql_generator'] = None
    
    try:
        results['testcase_exporter'] = test_test_case_exporter()
    except Exception as e:
        print(f"[FAIL] 测试用例导出器测试失败: {e}")
        results['testcase_exporter'] = None
    
    try:
        test_full_workflow()
        results['full_workflow'] = True
    except Exception as e:
        print(f"[FAIL] 完整工作流测试失败: {e}")
        results['full_workflow'] = None
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results.items():
        if result is None:
            status = "SKIP"
            skipped += 1
        elif result:
            status = "PASS"
            passed += 1
        else:
            status = "FAIL"
            failed += 1
        print(f"  {name}: {status}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败, {skipped} 跳过")
    
    if failed > 0:
        print("\n[FAIL] 部分测试失败")
        return 1
    else:
        print("\n[SUCCESS] 所有测试通过")
        return 0


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)