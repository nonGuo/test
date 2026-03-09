"""
分析器模块
"""
from .base_generator import BaseDesignGenerator
from .xmind_analyzer import XMindAnalyzer
from .xmind_template_loader import XMindTemplateLoader, TemplateNode
from .smart_generator import SmartChunkedGenerator, DesignGenerator
from .lightweight_generator import LightweightDesignGenerator

# 废弃的类（保留向后兼容）
from .template_based_generator import TemplateBasedDesignGenerator, HybridDesignGenerator

__all__ = [
    # 推荐使用
    'BaseDesignGenerator',
    'DesignGenerator',           # 主入口，推荐
    'SmartChunkedGenerator',     # DesignGenerator 的实际类
    'LightweightDesignGenerator', # 特殊场景：分层元数据
    # 工具类
    'XMindAnalyzer',
    'XMindTemplateLoader',
    'TemplateNode',
    # 废弃（向后兼容）
    'TemplateBasedDesignGenerator',  # 废弃，请使用 DesignGenerator
    'HybridDesignGenerator',         # 废弃，请使用 DesignGenerator
]
