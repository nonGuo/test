"""
智能分块测试设计生成器
根据内容长度自动选择最优生成策略
"""
import json
import re
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..models import TestDesign, TestNode
from .xmind_template_loader import XMindTemplateLoader, TemplateNode


# ============== Prompt 模板 ==============

# 一次生成全部 (适用于小型项目)
FULL_GENERATION_PROMPT = """
你是一位资深的数仓测试专家，请根据以下输入生成完整的测试设计。

## 输入信息

### 业务背景 (RS 文档)
{rs_content}

### 表模型设计 (TS 文档)
{ts_content}

### 字段加工规则 (Mapping 文档)
{mapping_content}

## XMind 模板结构

你必须严格按照以下模板层级结构生成测试设计：

{template_guide}

## 输出要求

1. **必须遵循模板层级**: 测试设计的树结构必须与 XMind 模板完全一致
2. **叶子节点填充**: 在每个叶子节点下，根据输入信息生成具体的测试点
3. **输出 JSON 格式**

```json
{{
  "root": "测试场景分析",
  "children": [
    {{
      "title": "L0-数据结果检查",
      "children": [...]
    }}
  ]
}}
```

请生成完整的测试设计 JSON：
"""

# 按分支生成 (适用于中型项目)
BRANCH_GENERATION_PROMPT = """
你是一位资深的数仓测试专家，请为以下测试分支生成测试设计。

## 当前分支
{branch_title}

## 分支模板结构
{branch_structure}

## 输入信息

### 业务背景 (RS 文档)
{rs_content}

### 表模型设计 (TS 文档)
{ts_content}

### 字段加工规则 (Mapping 文档)
{mapping_content}

## 输出要求

1. 为该分支下的每个叶子节点生成 1-2 个具体测试点
2. 标注优先级 (high/medium/low)
3. 添加测试要点描述 (20-50 字)
4. 如涉及具体表名，请替换模板中的占位符

```json
{{
  "title": "{branch_title}",
  "children": [...]
}}
```

请生成该分支的测试设计 JSON：
"""

# 按叶子节点生成 (适用于大型项目)
LEAF_GENERATION_PROMPT = """
你是一位资深的数仓测试专家，请为以下测试点生成具体内容。

## 测试点位置
{leaf_path}

## 测试点名称
{leaf_title}

## 上下文信息
{leaf_context}

## 输入信息

### 目标表
{target_table}

### 来源表
{source_tables}

### 相关字段
{relevant_fields}

### 相关 Mapping 规则
{relevant_mapping}

## 输出要求

生成 1-2 个具体测试点，包含:
- priority: 优先级 (high/medium/low)
- description: 测试要点描述 (20-50 字)
- tables: 涉及的表列表

```json
{{
  "title": "具体测试点名称",
  "priority": "high",
  "description": "测试要点描述",
  "tables": ["table1", "table2"]
}}
```

请生成测试点 JSON：
"""


class SmartChunkedGenerator:
    """智能分块测试设计生成器"""
    
    def __init__(self, llm_client: Any, template_path: str,
                 max_input_tokens: int = 8000,
                 strategy: str = "auto"):
        """
        初始化生成器
        
        Args:
            llm_client: LLM 客户端
            template_path: XMind 模板路径
            max_input_tokens: 最大输入 token 数
            strategy: 生成策略 (auto/full/by_branch/by_leaf)
        """
        self.llm_client = llm_client
        self.max_input_tokens = max_input_tokens
        self.strategy = strategy
        
        # 加载模板
        self.template_loader = XMindTemplateLoader(template_path)
        self.template_loader.load()
        
        # 统计信息
        self.stats = {
            "total_nodes": len(self.template_loader.node_map),
            "leaf_nodes": len(self.template_loader.leaf_nodes),
            "level_1_nodes": len(self.template_loader.get_nodes_by_level(1)),
            "max_level": max(self.template_loader.level_nodes.keys())
        }
    
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
        # 1. 估算内容长度
        input_tokens = self._estimate_tokens(rs_content + ts_content + mapping_content)
        output_tokens = self.stats["leaf_nodes"] * 150  # 每个叶子约 150 tokens
        
        print(f"[INFO] 内容估算：输入={input_tokens} tokens, 输出={output_tokens} tokens")
        print(f"[INFO] 模板统计：{self.stats}")
        
        # 2. 选择生成策略
        selected_strategy = self._select_strategy(input_tokens, output_tokens)
        print(f"[INFO] 选择策略：{selected_strategy}")
        
        # 3. 执行生成
        if selected_strategy == "full":
            design = self._generate_full(rs_content, ts_content, mapping_content)
        elif selected_strategy == "by_branch":
            design = self._generate_by_branch(rs_content, ts_content, mapping_content)
        elif selected_strategy == "by_leaf":
            design = self._generate_by_leaf(rs_content, ts_content, mapping_content)
        else:
            raise ValueError(f"未知策略：{selected_strategy}")
        
        return design
    
    def _select_strategy(self, input_tokens: int, output_tokens: int) -> str:
        """选择生成策略"""
        if self.strategy != "auto":
            return self.strategy
        
        total_tokens = input_tokens + output_tokens
        
        # 策略选择逻辑
        if total_tokens < self.max_input_tokens * 0.8:
            # 内容较少，一次生成
            return "full"
        
        elif self.stats["level_1_nodes"] <= 5:
            # 分支较少，按分支生成
            return "by_branch"
        
        else:
            # 内容很多，按叶子节点生成
            return "by_leaf"
    
    def _generate_full(self, rs: str, ts: str, mapping: str) -> TestDesign:
        """一次生成全部"""
        print("[INFO] 使用一次生成模式...")
        
        prompt = FULL_GENERATION_PROMPT.format(
            rs_content=rs,
            ts_content=ts,
            mapping_content=mapping,
            template_guide=self.template_loader.get_template_guide()
        )
        
        response = self.llm_client.generate(prompt)
        design_json = self._parse_json_response(response)
        
        return self._json_to_design(design_json)
    
    def _generate_by_branch(self, rs: str, ts: str, mapping: str) -> TestDesign:
        """按 Level 1 分支生成"""
        print("[INFO] 使用按分支生成模式...")
        
        level_1_nodes = self.template_loader.get_nodes_by_level(1)
        branch_results = []
        
        for branch in level_1_nodes:
            print(f"  生成分支：{branch.title}")
            
            # 提取分支的子树
            branch_template = self._template_node_to_dict(branch)
            
            # 生成该分支
            prompt = BRANCH_GENERATION_PROMPT.format(
                branch_title=branch.title,
                branch_structure=json.dumps(branch_template, ensure_ascii=False, indent=2),
                rs_content=self._compress_if_needed(rs),
                ts_content=self._compress_if_needed(ts),
                mapping_content=self._compress_if_needed(mapping)
            )
            
            response = self.llm_client.generate(prompt)
            branch_json = self._parse_json_response(response)
            branch_results.append(branch_json)
        
        # 合并所有分支
        design_json = {
            "root": "测试场景分析",
            "children": branch_results
        }
        
        return self._json_to_design(design_json)
    
    def _generate_by_leaf(self, rs: str, ts: str, mapping: str) -> TestDesign:
        """按叶子节点生成"""
        print("[INFO] 使用按叶子节点生成模式...")
        
        leaf_nodes = self.template_loader.get_leaf_nodes()
        leaf_results = []
        
        # 提取关键信息 (避免重复提取)
        target_table = self._extract_target_table(ts)
        source_tables = self._extract_source_tables(ts)
        fields = self._extract_fields(ts)
        mapping_rules = self._parse_mapping(mapping)
        
        for leaf in leaf_nodes:
            print(f"  生成叶子节点：{leaf.title}")
            
            # 提取相关信息
            relevant_info = self._extract_relevant_info(
                leaf_path=leaf.path,
                rs=rs, ts=ts, mapping=mapping,
                fields=fields, mapping_rules=mapping_rules
            )
            
            # 生成该叶子节点的内容
            prompt = LEAF_GENERATION_PROMPT.format(
                leaf_path=leaf.path,
                leaf_title=leaf.title,
                leaf_context=self._get_leaf_context(leaf.path),
                target_table=target_table,
                source_tables=", ".join(source_tables),
                relevant_fields=json.dumps(relevant_info["fields"], ensure_ascii=False),
                relevant_mapping=json.dumps(relevant_info["mapping"], ensure_ascii=False)
            )
            
            response = self.llm_client.generate(prompt)
            leaf_json = self._parse_json_response(response)
            
            leaf_results.append({
                "path": leaf.path,
                "content": leaf_json
            })
        
        # 组装完整设计
        design = self._assemble_from_leaf_results(leaf_results)
        return design
    
    def _generate_by_leaf_parallel(self, rs: str, ts: str, mapping: str, 
                                   max_workers: int = 5) -> TestDesign:
        """并行按叶子节点生成"""
        print(f"[INFO] 使用并行叶子节点生成模式 (workers={max_workers})...")
        
        leaf_nodes = self.template_loader.get_leaf_nodes()
        leaf_results = []
        
        # 预提取信息
        target_table = self._extract_target_table(ts)
        source_tables = self._extract_source_tables(ts)
        fields = self._extract_fields(ts)
        mapping_rules = self._parse_mapping(mapping)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            
            for i, leaf in enumerate(leaf_nodes):
                # 提取相关信息
                relevant_info = self._extract_relevant_info(
                    leaf_path=leaf.path,
                    rs=rs, ts=ts, mapping=mapping,
                    fields=fields, mapping_rules=mapping_rules
                )
                
                # 构建 Prompt
                prompt = LEAF_GENERATION_PROMPT.format(
                    leaf_path=leaf.path,
                    leaf_title=leaf.title,
                    leaf_context=self._get_leaf_context(leaf.path),
                    target_table=target_table,
                    source_tables=", ".join(source_tables),
                    relevant_fields=json.dumps(relevant_info["fields"], ensure_ascii=False),
                    relevant_mapping=json.dumps(relevant_info["mapping"], ensure_ascii=False)
                )
                
                # 提交任务
                future = executor.submit(self._generate_leaf_content, prompt, leaf.path)
                futures[future] = leaf
            
            # 收集结果
            for future in as_completed(futures):
                leaf = futures[future]
                try:
                    content = future.result()
                    leaf_results.append({
                        "path": leaf.path,
                        "content": content
                    })
                    print(f"  完成：{leaf.title}")
                except Exception as e:
                    print(f"  失败：{leaf.title} - {e}")
        
        # 组装完整设计
        design = self._assemble_from_leaf_results(leaf_results)
        return design
    
    def _generate_leaf_content(self, prompt: str, leaf_path: str) -> Dict:
        """生成单个叶子节点内容"""
        response = self.llm_client.generate(prompt)
        return self._parse_json_response(response)
    
    # ============== 辅助方法 ==============
    
    def _estimate_tokens(self, text: str) -> int:
        """估算 token 数 (中文字符约 1.5 tokens/字)"""
        return int(len(text) * 1.5)
    
    def _compress_if_needed(self, text: str, max_length: int = 2000) -> str:
        """如果文本过长则压缩"""
        if len(text) <= max_length:
            return text
        
        # 简单压缩：截取前 max_length 字
        return text[:max_length] + "... (内容已压缩)"
    
    def _parse_json_response(self, response: str) -> Dict:
        """解析 JSON 响应"""
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)
    
    def _json_to_design(self, json_data: Dict) -> TestDesign:
        """将 JSON 转换为 TestDesign"""
        root_node = TestNode(title=json_data.get("root", "测试场景分析"))
        self._build_nodes(json_data.get("children", []), root_node)
        return TestDesign(root=root_node)
    
    def _build_nodes(self, children: List[Dict], parent: TestNode) -> None:
        """递归构建节点"""
        for child_data in children:
            node = TestNode(
                title=child_data.get("title", ""),
                priority=child_data.get("priority", ""),
                description=child_data.get("description", ""),
                tables=child_data.get("tables", [])
            )
            parent.add_child(node)
            
            if "children" in child_data:
                self._build_nodes(child_data["children"], node)
    
    def _template_node_to_dict(self, node: TemplateNode) -> Dict:
        """将模板节点转换为字典"""
        return {
            "title": node.title,
            "level": node.level,
            "is_leaf": node.is_leaf,
            "children": [self._template_node_to_dict(c) for c in node.children]
        }
    
    def _extract_relevant_info(self, leaf_path: str, rs: str, ts: str, 
                               mapping: str, fields: List, 
                               mapping_rules: List) -> Dict:
        """提取与叶子节点相关的信息"""
        relevant_fields = []
        relevant_mapping = []
        
        # 根据路径判断测试类型
        if "主键" in leaf_path:
            relevant_fields = [f for f in fields if f.get("is_primary_key", False)]
            relevant_mapping = [m for m in mapping_rules 
                               if m.get("target_field") in [f["name"] for f in relevant_fields]]
        elif "度量" in leaf_path or "金额" in leaf_path or "数量" in leaf_path:
            relevant_fields = [f for f in fields if f.get("is_measure", False)]
            relevant_mapping = [m for m in mapping_rules 
                               if m.get("rule_type") in ["SUM", "COUNT", "AVG"]]
        elif "完整性" in leaf_path:
            relevant_fields = fields  # 所有字段
            relevant_mapping = mapping_rules
        elif "直取" in leaf_path:
            relevant_mapping = [m for m in mapping_rules if m.get("rule_type") == "DIRECT"]
            relevant_fields = [f for f in fields if f["name"] in [m["target_field"] for m in relevant_mapping]]
        else:
            # 默认使用全部信息
            relevant_fields = fields
            relevant_mapping = mapping_rules
        
        return {
            "fields": relevant_fields[:10],  # 限制数量
            "mapping": relevant_mapping[:10]
        }
    
    def _get_leaf_context(self, leaf_path: str) -> str:
        """获取叶子节点的上下文 (父节点路径)"""
        parts = leaf_path.split(">")
        if len(parts) > 1:
            return " -> ".join(parts[:-1])
        return ""
    
    def _extract_target_table(self, ts: str) -> str:
        """从 TS 中提取目标表名"""
        # 简单实现，实际需要根据 TS 格式解析
        import re
        match = re.search(r'目标表 [：:]\s*(\w+)', ts)
        if match:
            return match.group(1)
        return "UNKNOWN_TABLE"
    
    def _extract_source_tables(self, ts: str) -> List[str]:
        """从 TS 中提取来源表名"""
        import re
        matches = re.findall(r'来源表 [：:]\s*(\w+)', ts)
        return matches if matches else []
    
    def _extract_fields(self, ts: str) -> List:
        """从 TS 中提取字段列表"""
        # 简单实现，实际需要解析 TS 格式
        return [{"name": "field_name", "is_primary_key": False, "is_measure": False}]
    
    def _parse_mapping(self, mapping: str) -> List:
        """解析 Mapping 规则"""
        # 简单实现，实际需要解析 Mapping 格式
        return [{"source_field": "", "target_field": "", "rule_type": "DIRECT"}]
    
    def _assemble_from_leaf_results(self, leaf_results: List[Dict]) -> TestDesign:
        """从叶子节点结果组装完整设计"""
        # 创建根节点
        root_node = TestNode(title="测试场景分析")
        
        # 按路径组装
        for result in leaf_results:
            path = result["path"]
            content = result["content"]
            
            parts = path.split(">")
            current_node = root_node
            
            # 遍历路径，创建中间节点
            for i, part in enumerate(parts[:-1]):
                # 查找是否已存在该节点
                existing = next((c for c in current_node.children if c.title == part), None)
                if existing:
                    current_node = existing
                else:
                    # 创建新节点
                    new_node = TestNode(title=part)
                    current_node.add_child(new_node)
                    current_node = new_node
            
            # 添加叶子节点
            leaf_node = TestNode(
                title=parts[-1],
                priority=content.get("priority", "medium"),
                description=content.get("description", ""),
                tables=content.get("tables", [])
            )
            current_node.add_child(leaf_node)
        
        return TestDesign(root=root_node)
