"""
XMind 测试设计生成器
基于模板生成测试设计 XMind 文件
"""
import os
import tempfile
from typing import List, Optional
from ..models import TestDesign, TestNode


class XMindGenerator:
    """XMind 测试设计生成器"""

    def __init__(self, template_path: Optional[str] = None):
        """
        初始化生成器

        Args:
            template_path: XMind 模板文件路径，为空则使用内置空白模板
        """
        self.template_path = template_path
        self.workbook = None

    def create_workbook(self) -> None:
        """创建工作簿"""
        import xmind

        if self.template_path and os.path.exists(self.template_path):
            # 从模板加载
            self.workbook = xmind.load(self.template_path)
        else:
            # 使用现有的测试设计模板作为基础
            default_template = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                '测试设计模板.xmind'
            )
            if os.path.exists(default_template):
                self.workbook = xmind.load(default_template)
            else:
                # 创建空白工作簿 - 使用 xmind.load 从临时文件创建
                # 先创建一个临时的空 xmind 文件
                raise ValueError("需要提供模板文件，或确保测试设计模板.xmind存在于项目根目录")

    def generate(self, design: TestDesign, output_path: str) -> None:
        """
        生成测试设计 XMind 文件

        Args:
            design: 测试设计对象
            output_path: 输出文件路径
        """
        import xmind

        if not self.workbook:
            self.create_workbook()

        # 获取第一个 sheet
        sheet = self.workbook.getPrimarySheet()
        sheet.setTitle("测试场景分析")

        # 获取根主题
        root_topic = sheet.getRootTopic()
        root_topic.setTitle(design.root.title if design.root else "测试场景分析")

        # 清除原有子主题（如果有）
        # 注：xmind 库可能不支持直接删除，所以我们通过添加新内容覆盖

        # 构建树结构
        if design.root and design.root.children:
            self._build_topic_tree(root_topic, design.root.children)

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 保存文件
        xmind.save(self.workbook, output_path)

    def _build_topic_tree(self, parent_topic, children: List[TestNode]) -> None:
        """递归构建主题树"""
        for child in children:
            # 添加子主题
            child_topic = parent_topic.addSubTopic()
            child_topic.setTitle(child.title)

            # 添加标签 (label)
            if child.priority:
                try:
                    child_topic.addLabel(child.priority)
                except Exception:
                    pass  # 某些版本可能不支持

            # 添加备注 (notes)
            if child.description:
                try:
                    child_topic.setPlainNotes(child.description)
                except Exception:
                    pass

            # 递归构建子节点
            if child.children:
                self._build_topic_tree(child_topic, child.children)

    def generate_from_nodes(self, nodes: List[TestNode], output_path: str) -> None:
        """
        从节点列表生成 XMind

        Args:
            nodes: 测试节点列表
            output_path: 输出文件路径
        """
        import xmind

        if not self.workbook:
            self.create_workbook()

        sheet = self.workbook.getPrimarySheet()
        sheet.setTitle("测试设计")
        root_topic = sheet.getRootTopic()
        root_topic.setTitle("测试场景分析")

        for node in nodes:
            self._build_topic_tree(root_topic, [node])

        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        xmind.save(self.workbook, output_path)

    def load_and_modify(self, xmind_path: str) -> None:
        """
        加载已有的 XMind 文件进行修改

        Args:
            xmind_path: XMind 文件路径
        """
        import xmind
        self.workbook = xmind.load(xmind_path)

    def get_structure(self) -> dict:
        """获取当前工作簿的结构"""
        if not self.workbook:
            return {}

        sheet = self.workbook.getPrimarySheet()
        root = sheet.getRootTopic()

        return self._topic_to_dict(root)

    def _topic_to_dict(self, topic) -> dict:
        """主题转字典"""
        result = {
            "title": topic.getTitle() if hasattr(topic, 'getTitle') else str(topic),
            "children": []
        }

        if hasattr(topic, 'getSubTopics'):
            sub_topics = topic.getSubTopics() or []
            for sub in sub_topics:
                result["children"].append(self._topic_to_dict(sub))

        return result