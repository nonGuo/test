"""
AI 测试设计生成器
基于输入的 RS/TS/Mapping 文档生成测试设计
"""
import json
from typing import List, Dict, Any, Optional
from ..models import TestDesign, TestNode


# ============== Prompt 模板 ==============

TEST_DESIGN_PROMPT = """
你是一位资深的数仓测试专家，请根据以下输入生成测试设计。

## 输入信息

### 1. 业务背景 (RS 文档)
{rs_content}

### 2. 表模型设计 (TS 文档)
{ts_content}

### 3. 字段加工规则 (Mapping 文档)
{mapping_content}

## 输出要求

请按照以下 XMind 层级结构生成测试设计，输出 JSON 格式：

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
                    {{"title": "验证 F/I/TMP 表是否存在", "priority": "high", "description": "检查目标表是否已创建"}}
                  ]
                }}
              ]
            }}
          ]
        }},
        {{
          "title": "字段检查",
          "children": [
            {{
              "title": "数据完整性检查",
              "children": [
                {{"title": "验证字段级长度精度与 mapping 一致", "priority": "high", "description": "", "tables": []}}
              ]
            }},
            {{
              "title": "数据唯一性检查",
              "children": [
                {{"title": "验证直取类字段与源数据一致", "priority": "medium", "description": "", "tables": []}}
              ]
            }},
            {{
              "title": "数据有效性检查",
              "children": [
                {{
                  "title": "字段功能检查",
                  "children": [
                    {{
                      "title": "主外键类检查",
                      "children": [
                        {{"title": "验证主键字段空值率为 0", "priority": "high", "description": "", "tables": []}},
                        {{"title": "验证主键字段唯一", "priority": "high", "description": "", "tables": []}}
                      ]
                    }},
                    {{
                      "title": "度量类检查",
                      "children": [
                        {{"title": "验证度量字段 XX 空置率为 XX", "priority": "medium", "description": "", "tables": []}}
                      ]
                    }}
                  ]
                }}
              ]
            }}
          ]
        }}
      ]
    }},
    {{
      "title": "L1-配置/调度作业检查",
      "children": []
    }}
  ]
}}
```

## 生成规则

1. **必须覆盖的测试点**：
   - 表存在性检查
   - 字段完整性 (与 Mapping 一致)
   - 主键唯一性和非空检查
   - 度量值计算准确性检查

2. **根据表类型调整**：
   - 新建表：需要完整的测试覆盖
   - 变更表：重点关注变更字段和影响范围

3. **优先级标注**：
   - high: 主键、关键度量字段、核心业务逻辑
   - medium: 一般字段、派生字段
   - low: 辅助字段、备注类字段

4. **测试要点描述**：
   - 每个叶子节点需要有清晰的测试目的
   - 涉及具体表名和字段名

请生成完整的测试设计 JSON：
"""

TEST_CASE_GENERATION_PROMPT = """
你是一位数仓测试专家，请根据测试设计生成具体的测试用例 (包含 SQL 脚本)。

## 输入信息

### 1. 测试设计 (XMind 解析结果)
{design_content}

### 2. 表模型信息
- 目标表：{target_table}
- 来源表：{source_tables}
- 字段列表：{fields}

### 3. Mapping 规则
{mapping_rules}

## 输出要求

为每个叶子节点生成测试用例，输出 JSON 格式：

```json
[
  {{
    "case_id": "TC_001",
    "case_name": "目标表存在性检查",
    "category": "功能测试",
    "scene": "表/视图检查->存在性与权限检查",
    "priority": "high",
    "description": "验证目标表是否已创建",
    "tables": ["DWS_SALES_SUM"],
    "pre_condition": "ETL 作业已执行",
    "test_steps": "SELECT COUNT(*) FROM {target_table};",
    "expected_result": "查询成功，返回记录数>0",
    "post_condition": ""
  }}
]
```

## SQL 生成规则

### 1. 表存在性检查
```sql
SELECT COUNT(*) FROM {target_table};
```

### 2. 字段完整性检查
```sql
SELECT 
    COUNT(*) as total_cols
FROM INFORMATION_SCHEMA.COLUMNS 
WHERE TABLE_NAME = '{target_table}';
-- 与预期字段数对比
```

### 3. 主键唯一性检查
```sql
SELECT 
    {primary_key_field},
    COUNT(*) as cnt
FROM {target_table}
GROUP BY {primary_key_field}
HAVING COUNT(*) > 1;
-- 预期结果：返回 0 条记录
```

### 4. 主键非空检查
```sql
SELECT COUNT(*) 
FROM {target_table}
WHERE {primary_key_field} IS NULL;
-- 预期结果：返回 0 条记录
```

### 5. 数据一致性检查 (直取字段)
```sql
SELECT 
    a.{field},
    b.{field}
FROM {target_table} a
JOIN {source_table} b ON a.id = b.id
WHERE a.{field} <> b.{field};
-- 预期结果：返回 0 条记录
```

### 6. 度量值准确性检查
```sql
SELECT 
    SUM({measure_field}) as target_sum,
    (SELECT SUM({source_measure}) FROM {source_table}) as source_sum
FROM {target_table};
-- 预期结果：target_sum 与 source_sum 一致
```

请生成完整的测试用例 JSON：
"""


class AITestDesignGenerator:
    """AI 测试设计生成器"""
    
    def __init__(self, llm_client: Any):
        """
        初始化生成器
        
        Args:
            llm_client: LLM 客户端 (如 OpenAI/通义千问)
        """
        self.llm_client = llm_client
    
    def generate_design(self, rs_content: str, ts_content: str, 
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
        prompt = TEST_DESIGN_PROMPT.format(
            rs_content=rs_content,
            ts_content=ts_content,
            mapping_content=mapping_content
        )
        
        # 调用 LLM
        response = self.llm_client.generate(prompt)
        
        # 解析 JSON 响应
        design_json = self._parse_json_response(response)
        
        # 转换为 TestDesign 对象
        return self._json_to_design(design_json)
    
    def _parse_json_response(self, response: str) -> Dict:
        """解析 LLM 的 JSON 响应"""
        # 提取 JSON 部分 (可能包含在代码块中)
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)
    
    def _json_to_design(self, json_data: Dict) -> TestDesign:
        """将 JSON 转换为 TestDesign 对象"""
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
            
            # 递归处理子节点
            if "children" in child_data:
                self._build_nodes(child_data["children"], node)


class AITestCaseGenerator:
    """AI 测试用例生成器"""
    
    def __init__(self, llm_client: Any):
        """
        初始化生成器
        
        Args:
            llm_client: LLM 客户端
        """
        self.llm_client = llm_client
    
    def generate_test_cases(self, design: TestDesign, 
                           table_info: Dict,
                           mapping_rules: List[Dict]) -> List[Dict]:
        """
        基于测试设计生成测试用例
        
        Args:
            design: 测试设计对象
            table_info: 表信息
            mapping_rules: Mapping 规则
            
        Returns:
            测试用例列表
        """
        # 获取所有叶子节点
        leaf_nodes = design.get_all_leaf_nodes()
        
        # 构建 Prompt
        prompt = TEST_CASE_GENERATION_PROMPT.format(
            design_content=json.dumps([n.to_dict() for n in leaf_nodes], ensure_ascii=False),
            target_table=table_info.get("target_table", ""),
            source_tables=", ".join(table_info.get("source_tables", [])),
            fields=json.dumps(table_info.get("fields", []), ensure_ascii=False),
            mapping_rules=json.dumps(mapping_rules, ensure_ascii=False)
        )
        
        # 调用 LLM
        response = self.llm_client.generate(prompt)
        
        # 解析响应
        return self._parse_json_response(response)
    
    def _parse_json_response(self, response: str) -> List[Dict]:
        """解析 LLM 的 JSON 响应"""
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)
