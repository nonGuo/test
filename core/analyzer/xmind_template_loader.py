"""
XMind 模板加载器
动态加载和解析 XMind 模板结构，支持模板动态调整
"""
import xmindparser
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class TemplateNode:
    """模板节点"""
    title: str
    level: int
    path: str  # 完整路径，如 "测试场景分析>L0-数据结果检查>表/视图检查"
    children: List['TemplateNode'] = field(default_factory=list)
    parent: Optional['TemplateNode'] = field(default=None, repr=False)
    
    # 节点元数据
    node_id: str = ""  # 唯一标识，用于匹配
    is_leaf: bool = False
    depth: int = 0  # 从该节点到叶子节点的深度
    
    def add_child(self, child: 'TemplateNode'):
        child.parent = self
        self.children.append(child)
    
    def get_all_leaf_nodes(self) -> List['TemplateNode']:
        """获取所有叶子节点"""
        leaves = []
        self._collect_leaves(leaves)
        return leaves
    
    def _collect_leaves(self, leaves: List['TemplateNode']):
        if self.is_leaf:
            leaves.append(self)
        for child in self.children:
            child._collect_leaves(leaves)
    
    def get_path_parts(self) -> List[str]:
        """获取路径组成部分"""
        return self.path.split('>')
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "title": self.title,
            "level": self.level,
            "path": self.path,
            "node_id": self.node_id,
            "is_leaf": self.is_leaf,
            "depth": self.depth,
            "children": [c.to_dict() for c in self.children]
        }
    
    def __str__(self) -> str:
        return f"TemplateNode(title={self.title}, level={self.level}, is_leaf={self.is_leaf})"


class XMindTemplateLoader:
    """XMind 模板加载器"""
    
    def __init__(self, template_path: str):
        """
        初始化模板加载器
        
        Args:
            template_path: XMind 模板文件路径
        """
        self.template_path = template_path
        self.root: Optional[TemplateNode] = None
        self.node_map: Dict[str, TemplateNode] = {}  # path -> node
        self.leaf_nodes: List[TemplateNode] = []
        self.level_nodes: Dict[int, List[TemplateNode]] = {}  # level -> nodes
    
    def load(self) -> TemplateNode:
        """
        加载模板
        
        Returns:
            模板根节点
        """
        data = xmindparser.xmind_to_dict(self.template_path)
        
        # 获取第一个 sheet 的根主题
        sheet = data[0]
        root_topic = sheet['topic']
        
        # 构建模板树
        self.root = self._build_template_tree(root_topic, 0, "")
        
        # 构建索引
        self._build_index(self.root)
        
        return self.root
    
    def _build_template_tree(self, topic: Dict, level: int, parent_path: str) -> TemplateNode:
        """递归构建模板树"""
        title = topic.get('title', 'Unknown')
        path = f"{parent_path}>{title}" if parent_path else title
        
        # 创建节点
        node = TemplateNode(
            title=title,
            level=level,
            path=path,
            node_id=self._generate_node_id(path)
        )
        
        # 判断是否为叶子节点
        topics = topic.get('topics', [])
        node.is_leaf = len(topics) == 0
        
        # 递归处理子节点
        for child_topic in topics:
            child_node = self._build_template_tree(child_topic, level + 1, path)
            node.add_child(child_node)
        
        return node
    
    def _build_index(self, node: TemplateNode):
        """构建索引"""
        # 按路径索引
        self.node_map[node.path] = node
        
        # 按层级索引
        if node.level not in self.level_nodes:
            self.level_nodes[node.level] = []
        self.level_nodes[node.level].append(node)
        
        # 叶子节点列表
        if node.is_leaf:
            self.leaf_nodes.append(node)
        
        # 递归处理子节点
        for child in node.children:
            self._build_index(child)
    
    def _generate_node_id(self, path: str) -> str:
        """生成节点 ID"""
        # 使用路径的 MD5 或简化路径作为 ID
        import hashlib
        return hashlib.md5(path.encode('utf-8')).hexdigest()[:12]
    
    def get_node_by_path(self, path: str) -> Optional[TemplateNode]:
        """根据路径获取节点"""
        return self.node_map.get(path)
    
    def get_nodes_by_level(self, level: int) -> List[TemplateNode]:
        """获取指定层级的所有节点"""
        return self.level_nodes.get(level, [])
    
    def get_leaf_nodes(self) -> List[TemplateNode]:
        """获取所有叶子节点"""
        return self.leaf_nodes
    
    def get_structure_summary(self) -> Dict:
        """获取结构摘要"""
        return {
            "template_path": self.template_path,
            "max_level": max(self.level_nodes.keys()) if self.level_nodes else 0,
            "total_nodes": len(self.node_map),
            "leaf_nodes_count": len(self.leaf_nodes),
            "levels": {
                level: len(nodes) for level, nodes in self.level_nodes.items()
            }
        }
    
    def print_structure(self):
        """打印模板结构"""
        def _print_node(node: TemplateNode, indent: int = 0):
            prefix = "  " * indent
            marker = "[Leaf]" if node.is_leaf else "[Node]"
            print(f"{prefix}{marker} [{node.level}] {node.title}")
            for child in node.children:
                _print_node(child, indent + 1)
        
        if self.root:
            print("=" * 60)
            print("XMind 模板结构")
            print("=" * 60)
            _print_node(self.root)
            print("=" * 60)
    
    def export_to_json(self, output_path: str):
        """导出模板结构到 JSON"""
        if not self.root:
            raise ValueError("模板未加载")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.root.to_dict(), f, indent=2, ensure_ascii=False)
    
    def get_template_guide(self) -> str:
        """
        获取模板生成指南
        用于指导 AI 按照模板结构生成测试设计
        """
        if not self.root:
            raise ValueError("模板未加载")
        
        guide = []
        guide.append("请按照以下 XMind 模板结构生成测试设计：\n")
        
        def _build_guide(node: TemplateNode, indent: int = 0):
            prefix = "  " * indent
            if node.is_leaf:
                guide.append(f"{prefix}└─ {node.title} (叶子节点 - 需要生成具体测试点)")
            else:
                guide.append(f"{prefix}└─ {node.title} (分类节点)")
                for child in node.children:
                    _build_guide(child, indent + 1)
        
        _build_guide(self.root)
        
        return "\n".join(guide)
