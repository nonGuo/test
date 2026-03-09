"""
基于模板的测试设计生成器
动态加载 XMind 模板，按模板层级结构生成测试设计
"""
import json
import re
from typing import Dict, List, Any, Optional
from ..models import TestDesign, TestNode
from .base_generator import BaseDesignGenerator
from .xmind_template_loader import XMindTemplateLoader, TemplateNode


# ============== 动态 Prompt 模板 ==============

TEMPLATE_BASED_PROMPT = """
你是一位资深的数仓测试专家，请根据以下输入和**XMind 模板结构**生成测试设计。

## 输入信息

### 1. 业务背景 (RS 文档)
{rs_content}

### 2. 表模型设计 (TS 文档)
{ts_content}

### 3. 字段加工规则 (Mapping 文档)
{mapping_content}

## XMind 模板结构

你必须严格按照以下模板层级结构生成测试设计：

{template_guide}

## 模板节点说明

{template_nodes_json}

## 输出要求

1. **必须遵循模板层级**: 测试设计的树结构必须与 XMind 模板完全一致
2. **叶子节点填充**: 在每个叶子节点下，根据输入信息生成具体的测试点
3. **可新增叶子节点**: 如果模板的测试点覆盖不足，可以在对应分类下新增叶子节点
4. **输出 JSON 格式**: 

```json
{{
  "root": "测试场景分析",
  "children": [
    {{
      "title": "L0-数据结果检查",
      "children": [
        {{
          "title": "表/视图检查",
          "children": [
            {{
              "title": "存在性与权限检查",
              "children": [
                {{
                  "title": "目标存在性检查",
                  "children": [
                    {{"title": "验证 DWS_SALES_SUM 表是否存在", "priority": "high", "description": "检查目标表是否已创建", "tables": ["DWS_SALES_SUM"]}}
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

## 生成规则

1. **结构匹配**: 生成的测试设计必须包含模板中的所有节点
2. **叶子节点扩展**: 
   - 保留模板中的示例叶子节点
   - 根据实际表名、字段名替换模板中的占位符 (如 XX)
   - 根据需要新增叶子节点
3. **优先级标注**: 
   - high: 主键、关键度量、核心业务逻辑
   - medium: 一般字段、派生字段
   - low: 辅助字段
4. **测试要点描述**: 每个叶子节点需要有清晰的测试目的

请生成完整的测试设计 JSON：
"""


import warnings


class TemplateBasedDesignGenerator(BaseDesignGenerator):
    """
    基于模板的测试设计生成器
    
    .. deprecated::
        请使用 DesignGenerator 代替，它是 SmartChunkedGenerator 的别名，
        支持 strategy="full" 参数实现相同功能。
        
        迁移示例:
            # 旧代码
            generator = TemplateBasedDesignGenerator(llm_client, template_path)
            
            # 新代码
            generator = DesignGenerator(llm_client, template_path, strategy="full")
    """
    
    def __init__(self, llm_client: Any, template_path: str):
        warnings.warn(
            "TemplateBasedDesignGenerator 已废弃，请使用 DesignGenerator(strategy='full')",
            DeprecationWarning,
            stacklevel=2
        )
        self.llm_client = llm_client
        self.template_path = template_path

        # 加载模板
        self.template_loader = XMindTemplateLoader(template_path)
        self.template_loader.load()

    def generate(self, rs_content: str, ts_content: str,
                 mapping_content: str) -> TestDesign:
        """
        生成测试设计

        Args:
            rs_content: RS 文档内容
            ts_content: TS 文档内容
            mapping_content: Mapping 文档内容

        Returns:
            TestDesign: 测试设计对象
        """
        # 构建 Prompt
        prompt = TEMPLATE_BASED_PROMPT.format(
            rs_content=rs_content,
            ts_content=ts_content,
            mapping_content=mapping_content,
            template_guide=self.template_loader.get_template_guide(),
            template_nodes_json=json.dumps(
                self.template_loader.root.to_dict() if self.template_loader.root else {},
                ensure_ascii=False,
                indent=2
            )
        )

        # 调用 LLM
        response = self.llm_client.generate(prompt)

        # 解析 JSON 响应 (使用基类方法)
        design_json = self._parse_json_response(response)

        # 验证并转换 (使用基类的 _json_to_design)
        design = self._json_to_design(design_json)

        # 验证与模板的一致性
        self._validate_against_template(design)

        return design

    def _validate_against_template(self, design: TestDesign) -> bool:
        """
        验证生成的测试设计与模板结构的一致性

        Args:
            design: 生成的测试设计

        Returns:
            是否一致
        """
        if not self.template_loader.root:
            return True

        # 获取模板的所有非叶子节点路径
        template_paths = set()
        for node in self.template_loader.node_map.values():
            if not node.is_leaf:
                template_paths.add(node.path)

        # 获取生成设计的所有节点路径 (使用基类方法)
        design_paths = set()
        self._collect_design_paths(design.root, "", design_paths)

        # 检查是否包含所有模板节点
        missing_paths = template_paths - design_paths

        if missing_paths:
            print(f"⚠️  警告：生成的测试设计缺少以下模板节点:")
            for path in missing_paths:
                print(f"   - {path}")
            # 注意：不抛出异常，允许 AI 有灵活性

        return len(missing_paths) == 0
    
    def generate_structure_only(self) -> TestDesign:
        """
        仅生成模板结构 (用于初始化)
        
        Returns:
            只有模板结构的 TestDesign
        """
        return self._template_to_design(self.template_loader.root)
    
    def _template_to_design(self, template_node: TemplateNode) -> TestDesign:
        """将模板节点转换为测试设计"""
        if template_node is None:
            return TestDesign(root=TestNode(title="测试场景分析"))
        
        root_node = TestNode(title=template_node.title)
        self._convert_template_nodes(template_node, root_node)
        
        return TestDesign(root=root_node)
    
    def _convert_template_nodes(self, template_node: TemplateNode, 
                                 design_node: TestNode) -> None:
        """递归转换模板节点为设计节点"""
        for child_template in template_node.children:
            child_design = TestNode(
                title=child_template.title,
                priority="medium" if child_template.is_leaf else "",
                description="" if child_template.is_leaf else ""
            )
            design_node.add_child(child_design)
            
            # 递归处理
            self._convert_template_nodes(child_template, child_design)


class HybridDesignGenerator(BaseDesignGenerator):
    """
    混合生成器
    
    .. deprecated::
        该生成器已废弃。请使用 DesignGenerator 代替。
    """
    
    def __init__(self, llm_client: Any, template_path: str):
        warnings.warn(
            "HybridDesignGenerator 已废弃，请使用 DesignGenerator",
            DeprecationWarning,
            stacklevel=2
        )
        self.llm_client = llm_client
        self.template_loader = XMindTemplateLoader(template_path)
        self.template_loader.load()

    def generate(self, rs_content: str, ts_content: str,
                 mapping_content: str) -> TestDesign:
        """
        混合方式生成测试设计:
        1. 使用模板结构作为骨架
        2. AI 填充/扩展叶子节点
        """
        # 1. 生成模板骨架
        design = self.template_loader.root.to_dict()

        # 2. AI 填充叶子节点
        filled_design = self._fill_leaf_nodes(
            design, rs_content, ts_content, mapping_content
        )

        # 3. 转换为 TestDesign (使用基类方法)
        return self._json_to_design(filled_design)

    def _fill_leaf_nodes(self, structure: Dict, rs: str, ts: str,
                         mapping: str) -> Dict:
        """AI 填充叶子节点"""
        # 构建填充 Prompt
        prompt = f"""
请根据以下输入信息，为测试设计模板的每个叶子节点生成具体的测试内容。

【业务背景】{rs}
【表模型】{ts}
【Mapping 规则】{mapping}

【当前模板结构】
{json.dumps(structure, ensure_ascii=False, indent=2)}

请:
1. 为每个叶子节点添加 priority (high/medium/low)
2. 为每个叶子节点添加 description (测试要点)
3. 为每个叶子节点添加 tables (涉及表列表)
4. 如有需要，可在对应分类下新增叶子节点

输出完整的 JSON 结构：
"""
        response = self.llm_client.generate(prompt)
        return self._parse_json_response(response)
