"""
测试设计生成器基类
提取公共方法，消除重复代码
"""
import json
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from ..models import TestDesign, TestNode


class BaseDesignGenerator(ABC):
    """测试设计生成器基类"""

    @abstractmethod
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
        pass

    def _parse_json_response(self, response: str) -> Dict:
        """
        解析 LLM 的 JSON 响应

        支持以下格式：
        1. 纯 JSON 字符串
        2. 包含在 ```json ... ``` 代码块中的 JSON

        Args:
            response: LLM 响应字符串

        Returns:
            解析后的字典
        """
        # 尝试提取代码块中的 JSON
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response

        return json.loads(json_str)

    def _json_to_design(self, json_data: Dict) -> TestDesign:
        """
        将 JSON 数据转换为 TestDesign 对象

        Args:
            json_data: JSON 字典，包含 root 和 children

        Returns:
            TestDesign 对象
        """
        root_title = json_data.get("root", "测试场景分析")
        root_node = TestNode(title=root_title)
        self._build_nodes(json_data.get("children", []), root_node)
        return TestDesign(root=root_node)

    def _build_nodes(self, children: List[Dict], parent: TestNode) -> None:
        """
        递归构建测试节点树

        Args:
            children: 子节点数据列表
            parent: 父节点
        """
        for child_data in children:
            node = TestNode(
                title=child_data.get("title", ""),
                priority=child_data.get("priority", ""),
                description=child_data.get("description", ""),
                tables=child_data.get("tables", [])
            )
            # 保存测试类型（如果有）
            if "test_type" in child_data:
                node.test_type = child_data["test_type"]
            parent.add_child(node)

            # 递归处理子节点
            if "children" in child_data:
                self._build_nodes(child_data["children"], node)

    def _collect_design_paths(self, node: TestNode, parent_path: str, paths: set) -> None:
        """
        收集设计中的所有节点路径

        Args:
            node: 当前节点
            parent_path: 父路径
            paths: 路径集合
        """
        path = f"{parent_path}>{node.title}" if parent_path else node.title
        paths.add(path)

        for child in node.children:
            self._collect_design_paths(child, path, paths)