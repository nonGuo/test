"""
命令行入口
数仓测试用例生成工具
"""
import click
import os
import sys
from pathlib import Path
from typing import Optional

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@click.group()
@click.version_option(version='1.0.0', prog_name='数仓测试用例生成工具')
def cli():
    """数仓测试用例生成工具

    两阶段生成流程:
    1. 生成测试设计 (XMind) - 由 AI 基于文档生成，测试人员确认/修改
    2. 生成测试用例 (Excel) - 基于确认后的 XMind 生成完整测试用例

    \b
    快速开始:
        # 阶段一：生成测试设计
        python main.py generate-design --rs rs.docx --ts ts.docx --mapping mapping.xlsx

        # 阶段二：生成测试用例
        python main.py generate-testcases --xmind design.xmind --ts ts.docx --mapping mapping.xlsx
    """
    pass


@cli.command()
@click.option('--rs', 'rs_path', required=True, type=click.Path(exists=True),
              help='RS 设计文档路径 (.docx/.doc)')
@click.option('--ts', 'ts_path', required=True, type=click.Path(exists=True),
              help='TS 表模型文档路径 (.docx/.doc/.xlsx)')
@click.option('--mapping', 'mapping_path', required=True, type=click.Path(exists=True),
              help='Mapping 文档路径 (.xlsx)')
@click.option('--output', '-o', default='test_design.xmind',
              help='输出 XMind 文件路径 (默认: test_design.xmind)')
@click.option('--template', '-t', default=None, type=click.Path(exists=True),
              help='XMind 模板文件路径 (可选，用于动态模板适配)')
@click.option('--provider', '-p', default='qwen',
              type=click.Choice(['qwen', 'openai'], case_sensitive=False),
              help='AI 提供商 (默认: qwen)')
@click.option('--model', '-m', default='qwen-max',
              help='AI 模型名称 (默认: qwen-max)')
@click.option('--strategy', '-s', default='auto',
              type=click.Choice(['auto', 'full', 'by_branch', 'by_leaf'], case_sensitive=False),
              help='生成策略: auto(自动), full(一次生成), by_branch(按分支), by_leaf(按叶子)')
@click.option('--debug', is_flag=True, help='显示详细调试信息')
def generate_design(rs_path, ts_path, mapping_path, output, template,
                    provider, model, strategy, debug):
    """阶段一：生成测试设计 (XMind)

    基于 RS/TS/Mapping 文档生成测试设计，输出 XMind 文件供测试人员审查。

    \b
    示例:
        # 基本用法
        python main.py generate-design --rs rs.docx --ts ts.docx --mapping mapping.xlsx

        # 使用模板
        python main.py generate-design --rs rs.docx --ts ts.docx --mapping mapping.xlsx \\
            --template templates/测试设计模板.xmind

        # 指定输出路径
        python main.py generate-design --rs rs.docx --ts ts.docx --mapping mapping.xlsx\\
            -o output/design.xmind

        # 使用智能分块生成
        python main.py generate-design --rs rs.docx --ts ts.docx --mapping mapping.xlsx\\
            --strategy by_branch
    """
    click.echo("=" * 60)
    click.echo("🚀 阶段一：生成测试设计")
    click.echo("=" * 60)
    click.echo(f"   RS 文档：{rs_path}")
    click.echo(f"   TS 文档：{ts_path}")
    click.echo(f"   Mapping：{mapping_path}")
    click.echo(f"   AI 模型：{provider}/{model}")
    click.echo(f"   生成策略：{strategy}")
    if template:
        click.echo(f"   模板文件：{template}")
    click.echo("")

    try:
        # 1. 初始化 LLM 客户端
        click.echo("📦 初始化 AI 客户端...")
        from core.ai import LLMClientFactory
        llm_client = LLMClientFactory.create(provider, model=model)

        # 2. 解析输入文档
        click.echo("📄 解析输入文档...")
        rs_content = _parse_rs_document(rs_path, debug)
        ts_content = _parse_ts_document(ts_path, llm_client=llm_client, debug=debug)
        mapping_content = _parse_mapping_document(mapping_path, debug)

        if debug:
            click.echo(f"   RS 内容长度：{len(rs_content)} 字符")
            click.echo(f"   TS 内容长度：{len(ts_content)} 字符")
            click.echo(f"   Mapping 内容长度：{len(mapping_content)} 字符")

        # 3. 选择生成器并生成测试设计
        click.echo("🤖 AI 生成测试设计...")

        design = _generate_design(
            llm_client=llm_client,
            template_path=template,
            rs_content=rs_content,
            ts_content=ts_content,
            mapping_content=mapping_content,
            strategy=strategy,
            debug=debug
        )

        # 4. 生成 XMind 文件
        click.echo(f"💾 保存到 {output}...")

        # 确保输出目录存在
        output_dir = os.path.dirname(output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        from core.generator import XMindGenerator
        xmind_gen = XMindGenerator(template)
        xmind_gen.generate(design, output)

        # 5. 输出结果摘要
        leaf_nodes = design.get_all_leaf_nodes()
        click.echo("")
        click.echo("=" * 60)
        click.echo("✅ 测试设计已生成")
        click.echo("=" * 60)
        click.echo(f"   输出文件：{os.path.abspath(output)}")
        click.echo(f"   测试点数：{len(leaf_nodes)}")
        click.echo("")
        click.echo("📝 下一步：")
        click.echo("   1. 使用 XMind 打开生成的文件进行审查")
        click.echo("   2. 根据需要修改/补充/删除测试点")
        click.echo("   3. 保存确认后的文件")
        click.echo("   4. 运行 generate-testcases 命令生成测试用例")

    except ImportError as e:
        click.echo(f"❌ 导入错误：{e}", err=True)
        click.echo("   请确保已安装所有依赖：pip install -r requirements.txt", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 生成失败：{e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--xmind', '-x', required=True, type=click.Path(exists=True),
              help='已确认的测试设计 XMind 文件')
@click.option('--ts', 'ts_path', required=True, type=click.Path(exists=True),
              help='TS 表模型文档路径')
@click.option('--mapping', 'mapping_path', required=True, type=click.Path(exists=True),
              help='Mapping 文档路径')
@click.option('--output', '-o', default='test_cases.xlsx',
              help='输出 Excel 文件路径 (默认: test_cases.xlsx)')
@click.option('--provider', '-p', default='qwen',
              type=click.Choice(['qwen', 'openai'], case_sensitive=False),
              help='AI 提供商 (默认: qwen)')
@click.option('--model', '-m', default='qwen-max',
              help='AI 模型名称 (默认: qwen-max)')
@click.option('--debug', is_flag=True, help='显示详细调试信息')
def generate_testcases(xmind, ts_path, mapping_path, output,
                       provider, model, debug):
    """阶段二：生成测试用例 (Excel)

    基于已确认的测试设计 XMind 生成完整测试用例，包含 SQL 脚本和预期结果。

    \b
    示例:
        # 基本用法
        python main.py generate-testcases --xmind design.xmind --ts ts.docx --mapping mapping.xlsx

        # 指定输出路径
        python main.py generate-testcases --xmind design.xmind --ts ts.docx --mapping mapping.xlsx\\
            -o output/cases.xlsx
    """
    click.echo("=" * 60)
    click.echo("🚀 阶段二：生成测试用例")
    click.echo("=" * 60)
    click.echo(f"   测试设计：{xmind}")
    click.echo(f"   TS 文档：{ts_path}")
    click.echo(f"   Mapping：{mapping_path}")
    click.echo(f"   AI 模型：{provider}/{model}")
    click.echo("")

    try:
        # 1. 初始化 LLM 客户端
        click.echo("📦 初始化 AI 客户端...")
        from core.ai import LLMClientFactory
        llm_client = LLMClientFactory.create(provider, model=model)

        # 2. 解析 XMind 测试设计
        click.echo(f"📄 解析测试设计：{xmind}")
        from core.analyzer import XMindAnalyzer
        analyzer = XMindAnalyzer(xmind)
        design = analyzer.parse()

        if debug:
            leaf_nodes = design.get_all_leaf_nodes()
            click.echo(f"   叶子节点数：{len(leaf_nodes)}")

        # 3. 解析 TS 和 Mapping
        click.echo("📄 解析表模型和 Mapping...")
        ts_content = _parse_ts_document(ts_path, debug)
        mapping_result = _parse_mapping_document(mapping_path, debug, return_dict=True)

        # 提取表信息
        table_info = _extract_table_info(mapping_result)
        mapping_rules = mapping_result.get('field_mappings', [])

        if debug:
            click.echo(f"   目标表：{table_info.get('target_table', 'N/A')}")
            click.echo(f"   来源表：{table_info.get('source_tables', [])}")
            click.echo(f"   字段映射数：{len(mapping_rules)}")

        # 4. AI 生成测试用例
        click.echo("🤖 AI 生成测试用例...")
        from core.ai import AITestCaseGenerator
        testcase_generator = AITestCaseGenerator(llm_client)
        case_data_list = testcase_generator.generate_test_cases(
            design=design,
            table_info=table_info,
            mapping_rules=mapping_rules
        )

        # 5. 创建测试用例集并导出
        click.echo(f"💾 导出到 {output}...")

        # 确保输出目录存在
        output_dir = os.path.dirname(output)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        from core.models import TestCaseSuite
        from core.generator import TestCaseExporter, SQLGenerator

        suite = TestCaseSuite(
            name=f"测试用例集 - {table_info.get('target_table', 'unknown')}",
            target_table=table_info.get('target_table', 'unknown'),
            design_version=os.path.basename(xmind)
        )

        sql_generator = SQLGenerator()
        exporter = TestCaseExporter()

        for i, case_data in enumerate(case_data_list):
            # 生成用例编号
            if 'case_id' not in case_data or not case_data['case_id']:
                case_data['case_id'] = f"TC_{i+1:04d}"

            case = exporter.create_test_case_from_dict(case_data)

            # 优化 SQL (如果需要)
            if case.test_steps:
                try:
                    optimized_sql = sql_generator.generate_for_test_case(case_data)
                    case.test_steps = optimized_sql
                except Exception:
                    pass  # 保持原有 SQL

            suite.add_case(case)

        # 导出到 Excel
        exporter.export_to_excel(suite, output)

        # 6. 输出结果摘要
        click.echo("")
        click.echo("=" * 60)
        click.echo("✅ 测试用例已生成")
        click.echo("=" * 60)
        click.echo(f"   输出文件：{os.path.abspath(output)}")
        click.echo(f"   用例总数：{len(suite.cases)}")
        click.echo(f"   高优先级：{len(suite.get_cases_by_priority('high'))}")
        click.echo(f"   中优先级：{len(suite.get_cases_by_priority('medium'))}")
        click.echo(f"   低优先级：{len(suite.get_cases_by_priority('low'))}")

    except ImportError as e:
        click.echo(f"❌ 导入错误：{e}", err=True)
        click.echo("   请确保已安装所有依赖：pip install -r requirements.txt", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 生成失败：{e}", err=True)
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--xmind', '-x', required=True, type=click.Path(exists=True),
              help='XMind 文件路径')
@click.option('--output', '-o', type=click.Path(),
              help='输出 JSON 文件路径 (可选，默认输出到控制台)')
def analyze_xmind(xmind, output):
    """分析 XMind 文件结构 (调试用)

    \b
    示例:
        python main.py analyze-xmind --xmind design.xmind
        python main.py analyze-xmind --xmind design.xmind --output structure.json
    """
    click.echo(f"📊 分析 XMind 文件：{xmind}")
    click.echo("")

    try:
        from core.analyzer import XMindAnalyzer
        import json

        analyzer = XMindAnalyzer(xmind)
        structure = analyzer.get_structure_tree()

        # 打印树结构
        click.echo("=" * 60)
        click.echo("XMind 结构")
        click.echo("=" * 60)
        _print_tree(structure, 0)
        click.echo("=" * 60)

        # 统计信息
        leaf_count = _count_leaves(structure)
        total_count = _count_nodes(structure)
        max_depth = _get_max_depth(structure)

        click.echo(f"\n📊 统计信息:")
        click.echo(f"   总节点数：{total_count}")
        click.echo(f"   叶子节点数：{leaf_count}")
        click.echo(f"   最大深度：{max_depth}")

        # 导出到 JSON
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(structure, f, ensure_ascii=False, indent=2)
            click.echo(f"\n💾 结构已导出到：{output}")

    except Exception as e:
        click.echo(f"❌ 分析失败：{e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--template', '-t', type=click.Path(exists=True),
              help='XMind 模板文件路径')
def analyze_template(template):
    """分析 XMind 模板结构 (调试用)

    \b
    示例:
        python main.py analyze-template --template templates/测试设计模板.xmind
    """
    if not template:
        # 尝试使用默认模板
        default_template = PROJECT_ROOT / "测试设计模板.xmind"
        if default_template.exists():
            template = str(default_template)
        else:
            click.echo("❌ 请指定模板文件路径", err=True)
            sys.exit(1)

    click.echo(f"📊 分析 XMind 模板：{template}")
    click.echo("")

    try:
        from core.analyzer import XMindTemplateLoader
        import json

        loader = XMindTemplateLoader(template)
        loader.load()

        # 打印结构
        loader.print_structure()

        # 统计信息
        summary = loader.get_structure_summary()
        click.echo(f"\n📊 模板摘要:")
        click.echo(f"   模板路径：{summary['template_path']}")
        click.echo(f"   最大层级：{summary['max_level']}")
        click.echo(f"   总节点数：{summary['total_nodes']}")
        click.echo(f"   叶子节点数：{summary['leaf_nodes_count']}")

        click.echo(f"\n📋 各层节点数:")
        for level, count in sorted(summary['levels'].items()):
            click.echo(f"   Level {level}: {count} 个节点")

        # 打印模板指南
        click.echo(f"\n📝 模板指南 (用于 AI Prompt):")
        click.echo("-" * 40)
        guide = loader.get_template_guide()
        click.echo(guide)

    except Exception as e:
        click.echo(f"❌ 分析失败：{e}", err=True)
        sys.exit(1)


@cli.command()
def init():
    """初始化项目配置

    创建必要的目录结构和配置文件。
    """
    click.echo("🔧 初始化项目配置...")

    # 创建目录结构
    dirs_to_create = [
        "config/sql_templates",
        "templates",
        "output",
        "docs"
    ]

    created_dirs = []
    for dir_path in dirs_to_create:
        full_path = PROJECT_ROOT / dir_path
        if not full_path.exists():
            full_path.mkdir(parents=True)
            created_dirs.append(dir_path)

    # 创建默认配置文件
    config_file = PROJECT_ROOT / "config" / "prompts.yaml"
    if not config_file.exists():
        default_config = """# AI 配置
llm:
  provider: qwen
  model: qwen-max
  api_key: ${QWEN_API_KEY}
  temperature: 0.7
  max_tokens: 4096

# 生成策略
generator:
  strategy: auto  # auto/full/by_branch/by_leaf
  max_input_tokens: 8000
"""
        config_file.write_text(default_config, encoding='utf-8')
        click.echo(f"   创建配置文件：config/prompts.yaml")

    # 创建 .env 示例
    env_file = PROJECT_ROOT / ".env.example"
    if not env_file.exists():
        env_example = """# AI API Key 配置
# 通义千问
QWEN_API_KEY=your_qwen_api_key_here

# OpenAI
OPENAI_API_KEY=your_openai_api_key_here
"""
        env_file.write_text(env_example, encoding='utf-8')
        click.echo(f"   创建环境变量示例：.env.example")

    click.echo("")
    click.echo("✅ 项目配置已初始化")
    click.echo(f"   项目根目录：{PROJECT_ROOT}")

    if created_dirs:
        click.echo(f"   创建目录：")
        for d in created_dirs:
            click.echo(f"     - {d}")

    click.echo("")
    click.echo("📝 下一步：")
    click.echo("   1. 复制 .env.example 为 .env 并配置 API Key")
    click.echo("   2. 将 RS/TS/Mapping 文档放入 docs 目录")
    click.echo("   3. 将 XMind 模板放入 templates 目录 (可选)")
    click.echo("   4. 运行 generate-design 命令生成测试设计")


# ============== 辅助函数 ==============

def _parse_rs_document(file_path: str, debug: bool = False) -> str:
    """解析 RS 文档"""
    from core.parser.document_parser import RSParser

    parser = RSParser(debug=debug)
    result = parser.parse(file_path)

    # 使用 to_prompt_content 方法转换为 AI Prompt 格式
    return parser.to_prompt_content(result)


def _parse_ts_document(file_path: str, llm_client=None, debug: bool = False) -> str:
    """解析 TS 文档"""
    from core.parser.document_parser import TSParser

    parser = TSParser(debug=debug)
    result = parser.parse(file_path, llm_client=llm_client)

    # 使用 to_prompt_content 方法转换为 AI Prompt 格式
    return parser.to_prompt_content(result)


def _parse_mapping_document(file_path: str, debug: bool = False, return_dict: bool = False):
    """解析 Mapping 文档"""
    from core.parser import MappingParser

    parser = MappingParser(debug=debug)
    result = parser.parse(file_path)

    if return_dict:
        return result

    # 转换为字符串格式供 AI 使用
    if isinstance(result, dict):
        parts = []

        # 表映射
        if result.get('table_mappings'):
            table_strs = []
            for tm in result['table_mappings'][:10]:  # 限制显示数量
                table_strs.append(f"{tm.get('source_table', '')} -> {tm.get('target_table', '')}")
            parts.append(f"【表映射】\n" + "\n".join(table_strs))

        # 字段映射
        if result.get('field_mappings'):
            field_strs = []
            for fm in result['field_mappings'][:30]:  # 限制显示数量
                source = fm.get('source_field', '')
                target = fm.get('target_field', '')
                rule = fm.get('mapping_scene', '')
                transform = fm.get('transform_rule', '')[:50] if fm.get('transform_rule') else ''

                line = f"{source} -> {target}"
                if rule:
                    line += f" [{rule}]"
                if transform:
                    line += f" : {transform}..."
                field_strs.append(line)
            parts.append(f"【字段映射】\n" + "\n".join(field_strs))

        return "\n\n".join(parts) if parts else str(result)

    return str(result)


def _extract_table_info(mapping_result: dict) -> dict:
    """从 Mapping 结果中提取表信息"""
    return {
        'target_table': mapping_result.get('target_table', ''),
        'source_tables': mapping_result.get('source_tables', []),
        'fields': [
            {
                'name': fm.get('target_field'),
                'type': fm.get('target_field_type'),
                'source': fm.get('source_field'),
                'rule': fm.get('mapping_scene'),
                'transform': fm.get('transform_rule')
            }
            for fm in mapping_result.get('field_mappings', [])
            if fm.get('target_field')
        ]
    }


def _generate_design(llm_client, template_path, rs_content, ts_content,
                     mapping_content, strategy, debug):
    """根据策略生成测试设计"""
    from core.analyzer import DesignGenerator
    from core.ai import AITestDesignGenerator

    # 如果有模板，使用 DesignGenerator
    if template_path:
        generator = DesignGenerator(
            llm_client=llm_client,
            template_path=template_path,
            strategy=strategy
        )
        return generator.generate(rs_content, ts_content, mapping_content)
    else:
        # 无模板，使用传统生成器
        if debug:
            click.echo("   [DEBUG] 使用传统生成器 (无模板)")
        generator = AITestDesignGenerator(llm_client)
        return generator.generate_design(rs_content, ts_content, mapping_content)


def _print_tree(node: dict, level: int = 0):
    """打印树结构"""
    indent = "  " * level
    title = node.get('title', 'Unknown')

    # 判断是否叶子节点
    children = node.get('children', [])
    is_leaf = len(children) == 0
    marker = "📄" if is_leaf else "📁"

    click.echo(f"{indent}{marker} {title}")

    for child in children:
        _print_tree(child, level + 1)


def _count_leaves(node: dict) -> int:
    """计算叶子节点数"""
    children = node.get('children', [])
    if not children:
        return 1
    return sum(_count_leaves(child) for child in children)


def _count_nodes(node: dict) -> int:
    """计算总节点数"""
    children = node.get('children', [])
    return 1 + sum(_count_nodes(child) for child in children)


def _get_max_depth(node: dict, current_depth: int = 0) -> int:
    """计算最大深度"""
    children = node.get('children', [])
    if not children:
        return current_depth
    return max(_get_max_depth(child, current_depth + 1) for child in children)


if __name__ == '__main__':
    cli()