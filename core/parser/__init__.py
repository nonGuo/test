"""
解析器模块
"""
from .document_parser import (
    BaseParser,
    RSParser,
    TSParser,
    DWSTableMetadata,
    DocumentParserFactory
)
from .mapping_parser import (
    MappingParser,
    TableMapping,
    FieldMapping,
    ParseResult,
    parse_mapping_file,
    get_default_config_path
)
from .mapping_processor import (
    MappingProcessor,
    FieldMetadata,
    RuleSummary,
    DetailedLogic,
    RuleType
)
from .header_config import (
    HeaderConfigManager,
    ColumnMatch,
    create_header_config
)

__all__ = [
    # 基础解析器
    'BaseParser',
    'RSParser',
    'TSParser',
    'DWSTableMetadata',
    'DocumentParserFactory',
    # Mapping 解析器
    'MappingParser',
    'TableMapping',
    'FieldMapping',
    'ParseResult',
    'parse_mapping_file',
    'get_default_config_path',
    # Mapping 处理器
    'MappingProcessor',
    'FieldMetadata',
    'RuleSummary',
    'DetailedLogic',
    'RuleType',
    # 表头配置
    'HeaderConfigManager',
    'ColumnMatch',
    'create_header_config',
]