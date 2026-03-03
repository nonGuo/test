"""
XMind 测试设计解析器
解析已确认的测试设计 XMind 文件，为阶段二生成用例做准备
"""
import xmindparser
from typing import List, Dict, Any, Optional
from ..models import TestDesign, TestNode


class XMindAnalyzer:
    """XMind 测试设计分析器"""

    def __init__(self, xmind_path: str):
        """
        初始化分析器

        Args:
            xmind_path: XMind 文件路径
        """
        self.xmind_path = xmind_path
        self._data: Optional[Dict] = None

    def _load(self) -> Dict:
        """加载 XMind 文件"""
        if self._data is None:
            self._data = xmindparser.xmind_to_dict(self.xmind_path)
        return self._data

    def parse(self) -> TestDesign:
        """
        解析 XMind 文件为 TestDesign 对象

        Returns:
            TestDesign: 测试设计对象
        """
        data = self._load()

        # 获取第一个 sheet 的根主题
        sheet = data[0]
        root_topic = sheet['topic']

        # 创建根节点
        root_node = TestNode(title=root_topic.get('title', '测试场景分析'))

        # 递归解析子主题
        self._parse_topics(root_topic.get('topics', []), root_node)

        return TestDesign(root=root_node)

    def _parse_topics(self, topics: List[Dict], parent_node: TestNode) -> None:
        """递归解析主题"""
        if not topics:
            return

        for topic in topics:
            # 创建节点
            node = TestNode(title=topic.get('title', ''))

            # 解析标签 (labels)
            labels = topic.get('labels', [])
            if labels:
                # 查找优先级标签
                for label in labels:
                    label_lower = label.lower()
                    if label_lower in ['high', 'medium', 'low']:
                        node.priority = label_lower
                        break
                    elif 'high' in label_lower or '高' in label:
                        node.priority = 'high'
                        break
                    elif 'medium' in label_lower or '中' in label:
                        node.priority = 'medium'
                        break
                    elif 'low' in label_lower or '低' in label:
                        node.priority = 'low'
                        break

            # 解析备注 (notes)
            notes = topic.get('notes', '')
            if notes:
                node.description = notes

            # 解析标记 (markers) - 用于测试类型
            markers = topic.get('markers', [])
            if markers:
                marker_ids = [m.get('markerId', '') for m in markers]
                node.test_type = ";".join(marker_ids)

            # 添加到父节点
            parent_node.add_child(node)

            # 递归解析子主题
            sub_topics = topic.get('topics', [])
            if sub_topics:
                self._parse_topics(sub_topics, node)

    def get_leaf_nodes(self) -> List[TestNode]:
        """获取所有叶子节点 (最底层测试点)"""
        design = self.parse()
        return design.get_all_leaf_nodes()

    def get_structure_tree(self) -> Dict[str, Any]:
        """获取结构树 (用于调试)"""
        data = self._load()
        sheet = data[0]
        root_topic = sheet['topic']
        return self._topic_to_dict(root_topic)

    def _topic_to_dict(self, topic: Dict) -> Dict[str, Any]:
        """主题转字典"""
        result = {
            "title": topic.get('title', ''),
            "labels": topic.get('labels', []),
            "notes": topic.get('notes', ''),
            "children": []
        }

        sub_topics = topic.get('topics', [])
        for sub_topic in sub_topics:
            result["children"].append(self._topic_to_dict(sub_topic))

        return result

    def print_structure(self) -> None:
        """打印结构树 (调试用)"""
        tree = self.get_structure_tree()
        self._print_node(tree, 0)

    def _print_node(self, node: Dict, level: int) -> None:
        """打印节点"""
        indent = "  " * level
        children = node.get('children', [])
        marker = "📄" if not children else "📁"
        print(f"{indent}{marker} {node.get('title', '')}")

        for child in children:
            self._print_node(child, level + 1)