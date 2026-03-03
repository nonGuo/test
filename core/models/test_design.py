"""
测试设计数据模型
对应 XMind 模板的层级结构
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class TestLevel(Enum):
    """测试层级"""
    L0 = "L0-数据结果检查"
    L1 = "L1-配置/调度作业检查"


class CheckType(Enum):
    """检查类型"""
    TABLE_CHECK = "表/视图检查"
    FIELD_CHECK = "字段检查"
    JOB_CHECK = "配置/调度作业检查"


class FieldCheckType(Enum):
    """字段检查类型"""
    COMPLETENESS = "数据完整性检查"
    UNIQUENESS = "数据唯一性检查"
    VALIDITY = "数据有效性检查"


class FunctionCheckType(Enum):
    """功能检查类型"""
    PRIMARY_KEY = "主外键类检查"
    MEASURE = "度量类检查"


@dataclass
class TestNode:
    """测试设计节点 - 对应 XMind 节点"""
    title: str
    children: List['TestNode'] = field(default_factory=list)
    parent: Optional['TestNode'] = field(default=None, repr=False)
    
    # 元数据
    priority: str = ""  # high/medium/low
    test_type: str = ""  # 测试类型标签
    description: str = ""  # 测试要点描述
    tables: List[str] = field(default_factory=list)  # 涉及表
    
    def add_child(self, node: 'TestNode'):
        node.parent = self
        self.children.append(node)
    
    def get_path(self) -> str:
        """获取完整路径"""
        path = [self.title]
        current = self.parent
        while current:
            path.append(current.title)
            current = current.parent
        return " -> ".join(reversed(path))
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "title": self.title,
            "priority": self.priority,
            "test_type": self.test_type,
            "description": self.description,
            "tables": self.tables,
            "children": [child.to_dict() for child in self.children]
        }


@dataclass
class TestDesign:
    """测试设计 - 完整测试设计文档"""
    root: TestNode
    source_tables: List[str] = field(default_factory=list)
    target_table: str = ""
    mapping_rules: List[dict] = field(default_factory=list)
    
    def get_all_leaf_nodes(self) -> List[TestNode]:
        """获取所有叶子节点 (最底层测试点)"""
        leaves = []
        self._collect_leaves(self.root, leaves)
        return leaves
    
    def _collect_leaves(self, node: TestNode, leaves: List[TestNode]):
        if not node.children:
            leaves.append(node)
        else:
            for child in node.children:
                self._collect_leaves(child, leaves)
    
    def get_nodes_by_level(self, level: int) -> List[TestNode]:
        """获取指定层级的所有节点"""
        nodes = []
        self._collect_by_level(self.root, level, 0, nodes)
        return nodes
    
    def _collect_by_level(self, node: TestNode, target_level: int, 
                          current_level: int, nodes: List[TestNode]):
        if current_level == target_level:
            nodes.append(node)
        else:
            for child in node.children:
                self._collect_by_level(child, target_level, current_level + 1, nodes)
