"""
轻量级测试设计生成器
使用分层元数据，按需查询，避免上下文爆炸
"""
import json
import re
from typing import Dict, List, Any, Optional
from ..models import TestDesign, TestNode
from ..parser import MappingProcessor
from .base_generator import BaseDesignGenerator
from .xmind_template_loader import XMindTemplateLoader


# ============== Prompt 模板 ==============

# 阶段 1: 框架生成 (无 Mapping 细节)
FRAMEWORK_PROMPT = """
你是一位数仓测试专家，请根据业务背景生成测试框架。

## 业务背景 (RS 文档)
{rs_content}

## 测试设计模板
你必须严格按照以下模板层级结构生成测试框架：

{template_guide}

## 输出要求

1. 生成测试设计的树形结构
2. 不需要具体字段细节
3. 为每个叶子节点标注测试类型 (primary_key_check/measure_check/completeness_check 等)
4. 输出 JSON 格式

```json
{{
  "root": "测试场景分析",
  "children": [
    {{
      "title": "L0-数据结果检查",
      "children": [
        {{
          "title": "字段检查",
          "children": [
            {{
              "title": "数据有效性检查",
              "children": [
                {{
                  "title": "主外键类检查",
                  "children": [
                    {{"title": "验证主键字段空值率为 0", "test_type": "primary_key_null_check"}},
                    {{"title": "验证主键字段唯一", "test_type": "primary_key_unique_check"}}
                  ]
                }}
              ]
            }}
          ]
        }}
      ]
    }}
  ]
}}
```

请生成测试框架 JSON：
"""

# 阶段 2: 测试点填充 (Level 1 + Level 2 元数据)
TEST_POINT_PROMPT = """
你是一位数仓测试专家，请为以下测试类型生成具体测试点。

## 测试类型
{test_type}

## 相关字段摘要
{fields_summary}

## 模板节点
{template_node}

## 输出要求

1. 为每个相关字段生成 1-2 个具体测试点
2. 标注优先级 (high/medium/low)
3. 添加测试要点描述 (20-50 字)
4. 涉及具体表名和字段名

```json
{{
  "test_points": [
    {{
      "title": "验证 ORDER_ID 主键字段空值率为 0",
      "priority": "high",
      "description": "检查 ORDER_ID 字段无 NULL 值，确保主键完整性",
      "tables": ["DWS_ORDER_SUM"],
      "field": "ORDER_ID"
    }}
  ]
}}
```

请生成测试点 JSON：
"""

# 阶段 3: SQL 生成 (Level 3 详细逻辑)
SQL_GENERATION_PROMPT = """
你是一位 SQL 专家，请为以下字段生成测试 SQL。

## 字段信息
- 字段名：{field_name}
- 目标表：{target_table}

## 加工逻辑
{full_expression}

## 来源表
{source_tables}

## 测试要求
{test_requirement}

## 关联条件 (如有)
{join_conditions}

## 过滤条件 (如有)
{filter_conditions}

请生成验证 SQL(包含预期结果说明):
"""


class LightweightDesignGenerator(BaseDesignGenerator):
    """轻量级测试设计生成器"""

    def __init__(self, llm_client: Any, template_path: str,
                 mapping_processor: MappingProcessor):
        """
        初始化生成器

        Args:
            llm_client: LLM 客户端
            template_path: XMind 模板路径
            mapping_processor: Mapping 处理器 (已加载元数据)
        """
        self.llm_client = llm_client
        self.template_loader = XMindTemplateLoader(template_path)
        self.template_loader.load()
        self.mapping_processor = mapping_processor

        # 缓存已生成的测试点
        self.generated_points: Dict[str, List[Dict]] = {}
    
    def generate(self, rs_content: str) -> TestDesign:
        """
        生成完整测试设计 (三阶段)
        
        Args:
            rs_content: RS 文档内容
            
        Returns:
            TestDesign: 测试设计对象
        """
        print("[INFO] 开始生成测试设计 (轻量级)...")
        
        # 阶段 1: 生成框架
        print("  阶段 1: 生成测试框架...")
        framework = self._generate_framework(rs_content)
        
        # 阶段 2: 填充测试点
        print("  阶段 2: 填充测试点...")
        design = self._fill_test_points(framework)
        
        # 阶段 3: 生成 SQL (在测试用例生成阶段)
        # SQL 生成延迟到阶段二 (生成测试用例时)
        
        return design
    
    def _generate_framework(self, rs_content: str) -> TestDesign:
        """阶段 1: 生成测试框架"""
        prompt = FRAMEWORK_PROMPT.format(
            rs_content=rs_content,
            template_guide=self.template_loader.get_template_guide()
        )
        
        response = self.llm_client.generate(prompt)
        design_json = self._parse_json_response(response)
        
        return self._json_to_design(design_json)
    
    def _fill_test_points(self, design: TestDesign) -> TestDesign:
        """阶段 2: 填充测试点"""
        leaf_nodes = design.get_all_leaf_nodes()
        
        # 按测试类型分组
        test_types = {}
        for leaf in leaf_nodes:
            test_type = self._infer_test_type(leaf.title)
            if test_type not in test_types:
                test_types[test_type] = []
            test_types[test_type].append(leaf)
        
        print(f"    识别到 {len(test_types)} 种测试类型")
        
        # 对每种测试类型生成测试点
        for test_type, nodes in test_types.items():
            print(f"    处理测试类型：{test_type}")
            
            # 查询相关字段
            related_info = self.mapping_processor.query_by_test_type(test_type)
            
            if not related_info["fields"]:
                print(f"      ⚠️ 无相关字段，跳过")
                continue
            
            # 构建字段摘要
            fields_summary = json.dumps({
                "fields": related_info["fields"],
                "rules": related_info["rules"]
            }, ensure_ascii=False, indent=2)
            
            # 生成测试点
            for node in nodes:
                test_points = self._generate_test_points_for_node(
                    test_type=test_type,
                    fields_summary=fields_summary,
                    template_node=node.title
                )
                
                # 将测试点添加到节点
                for tp in test_points:
                    child_node = TestNode(
                        title=tp.get("title", node.title),
                        priority=tp.get("priority", "medium"),
                        description=tp.get("description", ""),
                        tables=tp.get("tables", [])
                    )
                    node.add_child(child_node)
                
                # 缓存
                self.generated_points[node.title] = test_points
        
        return design
    
    def _generate_test_points_for_node(self, test_type: str, 
                                       fields_summary: str,
                                       template_node: str) -> List[Dict]:
        """为单个节点生成测试点"""
        prompt = TEST_POINT_PROMPT.format(
            test_type=test_type,
            fields_summary=fields_summary,
            template_node=template_node
        )
        
        response = self.llm_client.generate(prompt)
        result = self._parse_json_response(response)
        
        return result.get("test_points", [])
    
    def generate_test_sql(self, field_name: str, 
                          test_requirement: str) -> str:
        """
        阶段 3: 生成测试 SQL (按需)
        
        Args:
            field_name: 字段名
            test_requirement: 测试要求
            
        Returns:
            SQL 脚本
        """
        # 获取详细逻辑
        detail = self.mapping_processor.get_level3_detail(field_name)
        
        if not detail:
            return f"-- 未找到字段 {field_name} 的加工逻辑"
        
        prompt = SQL_GENERATION_PROMPT.format(
            field_name=field_name,
            target_table=detail.target_field.split('.')[0] if '.' in detail.target_field else "UNKNOWN",
            full_expression=detail.full_expression,
            source_tables=", ".join(detail.source_tables),
            test_requirement=test_requirement,
            join_conditions="\n".join(detail.join_conditions) if detail.join_conditions else "无",
            filter_conditions="\n".join(detail.filter_conditions) if detail.filter_conditions else "无"
        )
        
        response = self.llm_client.generate(prompt)
        return self._extract_sql(response)
    
    # ============== 辅助方法 ==============
    
    # 注：以下方法由基类 BaseDesignGenerator 提供
    # _parse_json_response, _json_to_design, _build_nodes

    def _infer_test_type(self, node_title: str) -> str:
        """根据节点标题推断测试类型"""
        title = node_title.upper()
        
        if "主键" in title or "PRIMARY" in title:
            return "primary_key_check"
        elif "唯一" in title or "UNIQUE" in title:
            return "unique_check"
        elif "空值" in title or "NULL" in title:
            return "null_check"
        elif "度量" in title or "SUM" in title or "COUNT" in title:
            return "measure_aggregation"
        elif "完整性" in title or "COMPLETENESS" in title:
            return "completeness_check"
        elif "一致性" in title or "CONSISTENCY" in title:
            return "consistency_check"
        elif "存在" in title or "EXISTS" in title:
            return "table_exists_check"
        elif "权限" in title or "PERMISSION" in title:
            return "permission_check"
        else:
            return "general_check"
    
    def _extract_sql(self, response: str) -> str:
        """从响应中提取 SQL"""
        sql_match = re.search(r'```sql\s*(.*?)\s*```', response, re.DOTALL)
        if sql_match:
            return sql_match.group(1).strip()
        return response.strip()
    
    def get_metadata_summary(self) -> Dict:
        """获取元数据摘要"""
        return self.mapping_processor.get_metadata_summary()
