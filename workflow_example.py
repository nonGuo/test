"""
完整流程示例
演示从文档到测试用例的完整生成流程
"""
import os
from core.parser import DocumentParserFactory
from core.ai import AITestDesignGenerator, AITestCaseGenerator, LLMClientFactory
from core.generator import XMindGenerator, SQLGenerator, TestCaseExporter
from core.analyzer import XMindAnalyzer, TemplateBasedDesignGenerator, HybridDesignGenerator
from core.models import TestCase, TestCaseSuite


class TestDesignWorkflow:
    """测试设计生成工作流"""
    
    def __init__(self, llm_provider: str = "qwen", model: str = "qwen-max",
                 template_path: str = None):
        """
        初始化工作流
        
        Args:
            llm_provider: LLM 提供商
            model: 模型名称
            template_path: XMind 模板路径 (用于动态模板适配)
        """
        # 创建 LLM 客户端
        self.llm_client = LLMClientFactory.create(llm_provider, model=model)
        
        # 保存模板路径
        self.template_path = template_path
        
        # 根据是否有模板选择生成器
        if template_path:
            # 使用基于模板的生成器 (推荐)
            self.design_generator = TemplateBasedDesignGenerator(
                self.llm_client, template_path
            )
            print(f"[INFO] 使用基于模板的生成器：{template_path}")
        else:
            # 使用传统生成器
            self.design_generator = AITestDesignGenerator(self.llm_client)
            print("[INFO] 使用传统生成器 (无模板)")
        
        # 测试用例生成器
        self.testcase_generator = AITestCaseGenerator(self.llm_client)
        self.xmind_generator = XMindGenerator(template_path)
        self.sql_generator = SQLGenerator()
        self.exporter = TestCaseExporter()
    
    def stage1_generate_design(self, rs_path: str, ts_path: str, 
                               mapping_path: str, output_path: str) -> str:
        """
        阶段一：生成测试设计
        
        Args:
            rs_path: RS 文档路径
            ts_path: TS 文档路径
            mapping_path: Mapping 文档路径
            output_path: 输出 XMind 路径
            
        Returns:
            输出文件路径
        """
        print("🚀 阶段一：生成测试设计")
        
        # 1. 解析输入文档
        print("   📄 解析文档...")
        docs = DocumentParserFactory.parse_all(rs_path, ts_path, mapping_path)
        
        # 2. AI 生成测试设计
        print("   🤖 AI 生成测试设计...")
        design = self.design_generator.generate_design(
            rs_content=str(docs["rs"]),
            ts_content=str(docs["ts"]),
            mapping_content=str(docs["mapping"])
        )
        
        # 3. 生成 XMind 文件
        print(f"   💾 保存到 {output_path}...")
        self.xmind_generator.generate(design, output_path)
        
        print(f"✅ 测试设计已生成：{output_path}")
        print("   📝 请使用 XMind 打开审查并确认设计")
        
        return output_path
    
    def stage2_generate_testcases(self, xmind_path: str, 
                                  ts_path: str, mapping_path: str,
                                  output_path: str) -> str:
        """
        阶段二：生成测试用例
        
        Args:
            xmind_path: 已确认的 XMind 文件路径
            ts_path: TS 文档路径
            mapping_path: Mapping 文档路径
            output_path: 输出 Excel 路径
            
        Returns:
            输出文件路径
        """
        print("🚀 阶段二：生成测试用例")
        
        # 1. 解析 XMind 测试设计
        print(f"   📄 解析测试设计：{xmind_path}")
        analyzer = XMindAnalyzer(xmind_path)
        design = analyzer.parse()
        
        # 2. 解析 TS 和 Mapping 获取表信息
        print("   📄 解析表模型和 Mapping...")
        ts_parser = DocumentParserFactory.get_parser("TS")
        mapping_parser = DocumentParserFactory.get_parser("MAPPING")
        
        table_info = ts_parser.parse(ts_path)
        mapping_rules = mapping_parser.parse(mapping_path)
        
        # 3. AI 生成测试用例
        print("   🤖 AI 生成测试用例...")
        case_data_list = self.testcase_generator.generate_test_cases(
            design=design,
            table_info=table_info,
            mapping_rules=mapping_rules
        )
        
        # 4. 创建测试用例集
        suite = TestCaseSuite(
            name=f"测试用例集 - {table_info.get('target_table', 'unknown')}",
            target_table=table_info.get('target_table', 'unknown'),
            design_version=os.path.basename(xmind_path)
        )
        
        for case_data in case_data_list:
            case = self.exporter.create_test_case_from_dict(case_data)
            
            # 使用 SQL 生成器优化 SQL
            try:
                sql = self.sql_generator.generate_for_test_case(case_data)
                case.test_steps = sql
            except Exception as e:
                print(f"   ⚠️  SQL 生成失败：{e}")
            
            suite.add_case(case)
        
        # 5. 导出到 Excel
        print(f"   💾 导出到 {output_path}...")
        self.exporter.export_to_excel(suite, output_path)
        
        print(f"✅ 测试用例已生成：{output_path}")
        print(f"   📊 共生成 {len(suite.cases)} 条测试用例")
        
        return output_path
    
    def run_full_workflow(self, rs_path: str, ts_path: str, 
                          mapping_path: str, 
                          design_output: str = "test_design.xmind",
                          testcase_output: str = "test_cases.xlsx",
                          auto_confirm: bool = False) -> None:
        """
        运行完整工作流
        
        Args:
            rs_path: RS 文档路径
            ts_path: TS 文档路径
            mapping_path: Mapping 文档路径
            design_output: 测试设计输出路径
            testcase_output: 测试用例输出路径
            auto_confirm: 是否自动确认 (跳过人工审查)
        """
        # 阶段一
        design_path = self.stage1_generate_design(
            rs_path, ts_path, mapping_path, design_output
        )
        
        if not auto_confirm:
            # 等待人工确认
            print("\n" + "=" * 50)
            print("请审查测试设计文件:")
            print(f"  {design_path}")
            print("\n审查完成后，按 Enter 继续...")
            input()
        
        # 阶段二
        self.stage2_generate_testcases(
            design_path, ts_path, mapping_path, testcase_output
        )


# 使用示例
if __name__ == "__main__":
    # 创建工作流
    workflow = TestDesignWorkflow(llm_provider="qwen", model="qwen-max")
    
    # 运行完整流程 (自动确认模式)
    # workflow.run_full_workflow(
    #     rs_path="docs/RS_设计文档.docx",
    #     ts_path="docs/TS_表模型.docx",
    #     mapping_path="docs/Mapping 规则.xlsx",
    #     design_output="output/test_design.xmind",
    #     testcase_output="output/test_cases.xlsx",
    #     auto_confirm=False  # 实际使用建议设为 False
    )
    
    # 或者分阶段运行:
    
    # 阶段一
    # workflow.stage1_generate_design(
    #     rs_path="docs/RS_设计文档.docx",
    #     ts_path="docs/TS_表模型.docx",
    #     mapping_path="docs/Mapping 规则.xlsx",
    #     output_path="output/test_design.xmind"
    # )
    
    # [人工审查 XMind 文件后]
    
    # 阶段二
    # workflow.stage2_generate_testcases(
    #     xmind_path="output/test_design_confirmed.xmind",
    #     ts_path="docs/TS_表模型.docx",
    #     mapping_path="docs/Mapping 规则.xlsx",
    #     output_path="output/test_cases.xlsx"
    # )
