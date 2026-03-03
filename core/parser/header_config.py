"""
表头配置管理器
支持灵活适配不同表头的 Mapping 文档

特性：
1. 内置默认列名映射配置
2. 支持外部 YAML 配置文件覆盖
3. 多级匹配策略：完全匹配 → 别名匹配 → 模糊匹配
"""
import os
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import yaml


@dataclass
class ColumnMatch:
    """列匹配结果"""
    standard_name: str      # 标准列名
    actual_name: str        # 实际列名
    index: int              # 列索引
    match_type: str         # 匹配类型: exact/alias/fuzzy


class HeaderConfigManager:
    """
    表头配置管理器
    
    使用方式：
    1. 使用内置默认配置
    2. 加载外部 YAML 配置文件覆盖默认配置
    3. 运行时动态添加自定义映射
    """
    
    # ============== 内置默认配置 ==============
    
    # 表结构映射页签的列名映射
    DEFAULT_TABLE_MAPPING_HEADERS = {
        'group_id': ['序号', 'ID', '编号', 'id', 'No'],
        'group': ['分组', '组', 'Group', 'group_id'],
        'source_schema': ['来源schema', '来源 schema', '源schema', 'source_schema', '源模式', '来源库'],
        'source_table': ['来源表英文名', '来源表', '源表英文名', 'source_table', '源表', 'source_table_name'],
        'source_table_cn': ['来源表中文名', '来源表中文', '源表中文名', 'source_table_cn', '源表中文', '来源表中文名称'],
        'source_alias': ['来源表别名', '源表别名', 'source_alias', '别名', 'alias', '表别名'],
        'target_schema': ['目标schema', '目标 schema', 'target_schema', '目标模式', '目标库'],
        'target_table': ['目标表英文名', '目标表', 'target_table', '目标表名', 'target_table_name'],
        'target_table_cn': ['目标表中文名', '目标表中文', 'target_table_cn', '目标表中文名称'],
        'filter_condition': ['取数条件', '过滤条件', 'filter_condition', 'where', '筛选条件', '过滤'],
        'join_condition': ['关联条件', 'join_condition', '连接条件', 'join', '关联'],
    }
    
    # 字段级映射页签的列名映射
    DEFAULT_FIELD_MAPPING_HEADERS = {
        'group_id': ['序号', 'ID', '编号', 'id', 'No'],
        'group': ['分组', '组', 'Group', 'group_id'],
        'source_schema': ['来源schema', '来源 schema', '源schema', 'source_schema', '源模式', '来源库'],
        'source_table': ['来源表英文名', '来源表', '源表英文名', 'source_table', '源表', 'source_table_name'],
        'source_alias': ['来源表别名', '源表别名', 'source_alias', '别名', 'alias', '表别名'],
        'source_field': ['来源表字段英文名', '来源字段英文名', 'source_field', '来源字段', '源字段', '字段英文名', 'source_column', '源字段名'],
        'source_field_cn': ['来源表字段中文名', '来源字段中文名', 'source_field_cn', '来源字段中文', '源字段中文', '字段中文名', 'source_column_cn'],
        'source_field_type': ['来源表字段类型', '来源字段类型', 'source_field_type', '字段类型', '类型', 'source_data_type', '源字段类型'],
        'mapping_scene': ['映射场景', '场景', 'mapping_scene', '加工类型', '转换类型', '映射类型', 'scene'],
        'transform_rule': ['具体加工规则', '加工规则', 'transform_rule', '转换规则', '规则', '计算规则', '加工逻辑', 'transformation'],
        'target_schema': ['目标schema', '目标 schema', 'target_schema', '目标模式', '目标库'],
        'target_table': ['目标表英文名', '目标表', 'target_table', '目标表名', 'target_table_name'],
        'target_field': ['目标表字段英文名', '目标字段英文名', 'target_field', '目标字段', '字段英文名', 'target_column', '目标字段名'],
        'target_field_cn': ['目标表字段中文名', '目标字段中文名', 'target_field_cn', '目标字段中文', '字段中文名', 'target_column_cn'],
        'target_field_type': ['目标表字段类型', '目标字段类型', 'target_field_type', '字段类型', '类型', 'target_data_type'],
    }
    
    # 页签名称映射
    DEFAULT_SHEET_NAME_MAPPING = {
        'table': ['表结构映射', '表映射', 'table_mapping', '表关系', '来源表关系', '表结构', 'table'],
        'field': ['字段级映射', '字段映射', 'field_mapping', '字段加工', '字段规则', '字段', 'field'],
    }
    
    # 关键词模糊匹配配置（用于模糊匹配时的关键词识别）
    FUZZY_KEYWORDS = {
        'source_schema': ['来源', '源', 'schema', '库'],
        'source_table': ['来源表', '源表', 'source table'],
        'source_field': ['来源字段', '源字段', 'source field', 'source column'],
        'target_schema': ['目标', 'schema', '库'],
        'target_table': ['目标表', 'target table'],
        'target_field': ['目标字段', 'target field', 'target column'],
        'transform_rule': ['加工规则', '转换规则', '规则', 'transform', 'rule'],
        'mapping_scene': ['映射场景', '场景', 'scene'],
        'join_condition': ['关联条件', 'join', '连接'],
        'filter_condition': ['取数条件', '过滤条件', 'filter', 'where'],
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器
        
        Args:
            config_path: 外部配置文件路径，可选
        """
        self.table_mapping_headers = self.DEFAULT_TABLE_MAPPING_HEADERS.copy()
        self.field_mapping_headers = self.DEFAULT_FIELD_MAPPING_HEADERS.copy()
        self.sheet_name_mapping = self.DEFAULT_SHEET_NAME_MAPPING.copy()
        
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> None:
        """
        加载外部配置文件
        
        Args:
            config_path: YAML 配置文件路径
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            if not config:
                return
            
            # 加载表结构映射配置
            if 'table_mapping' in config:
                for key, aliases in config['table_mapping'].items():
                    if isinstance(aliases, list):
                        if key in self.table_mapping_headers:
                            # 合并配置，外部配置优先
                            self.table_mapping_headers[key] = aliases + [
                                a for a in self.table_mapping_headers[key] 
                                if a not in aliases
                            ]
                        else:
                            self.table_mapping_headers[key] = aliases
            
            # 加载字段级映射配置
            if 'field_mapping' in config:
                for key, aliases in config['field_mapping'].items():
                    if isinstance(aliases, list):
                        if key in self.field_mapping_headers:
                            self.field_mapping_headers[key] = aliases + [
                                a for a in self.field_mapping_headers[key] 
                                if a not in aliases
                            ]
                        else:
                            self.field_mapping_headers[key] = aliases
            
            # 加载页签名称配置
            if 'sheet_names' in config:
                for key, names in config['sheet_names'].items():
                    if isinstance(names, list):
                        if key in self.sheet_name_mapping:
                            self.sheet_name_mapping[key] = names + [
                                n for n in self.sheet_name_mapping[key] 
                                if n not in names
                            ]
                        else:
                            self.sheet_name_mapping[key] = names
                            
        except Exception as e:
            print(f"[Warning] 加载配置文件失败: {e}，使用默认配置")
    
    def add_custom_alias(self, mapping_type: str, column_name: str, alias: str) -> None:
        """
        动态添加自定义别名
        
        Args:
            mapping_type: 'table' 或 'field'
            column_name: 标准列名
            alias: 新增别名
        """
        headers = self._get_headers(mapping_type)
        if column_name in headers:
            if alias not in headers[column_name]:
                headers[column_name].insert(0, alias)  # 插入到最前面，优先匹配
    
    def _get_headers(self, mapping_type: str) -> Dict[str, List[str]]:
        """获取对应类型的表头配置"""
        if mapping_type == 'table':
            return self.table_mapping_headers
        elif mapping_type == 'field':
            return self.field_mapping_headers
        else:
            raise ValueError(f"未知的映射类型: {mapping_type}")
    
    def normalize_header(self, header: str) -> str:
        """
        标准化表头名称（去除空格、转小写）
        
        Args:
            header: 原始表头名
            
        Returns:
            标准化后的表头名
        """
        if header is None:
            return ''
        # 去除空格、下划线等，转小写
        return re.sub(r'[\s_\-]+', '', str(header)).lower()
    
    def find_column(
        self, 
        headers: List[str], 
        standard_name: str, 
        mapping_type: str = 'field'
    ) -> ColumnMatch:
        """
        在表头中查找指定列
        
        Args:
            headers: 实际表头列表
            standard_name: 标准列名
            mapping_type: 映射类型 ('table' 或 'field')
            
        Returns:
            ColumnMatch 对象，包含匹配结果
        """
        headers_dict = self._get_headers(mapping_type)
        alias_list = headers_dict.get(standard_name, [])
        
        # 标准化后的表头列表
        normalized_headers = [self.normalize_header(h) for h in headers]
        
        # 第一级：完全匹配（标准化后完全相等）
        for i, norm_h in enumerate(normalized_headers):
            for alias in alias_list:
                if self.normalize_header(alias) == norm_h:
                    return ColumnMatch(
                        standard_name=standard_name,
                        actual_name=headers[i],
                        index=i,
                        match_type='exact'
                    )
        
        # 第二级：别名匹配（标准化后包含关系，别名在前）
        for i, norm_h in enumerate(normalized_headers):
            for alias in alias_list:
                norm_alias = self.normalize_header(alias)
                if norm_alias and (norm_alias in norm_h or norm_h in norm_alias):
                    return ColumnMatch(
                        standard_name=standard_name,
                        actual_name=headers[i],
                        index=i,
                        match_type='alias'
                    )
        
        # 第三级：关键词模糊匹配
        if standard_name in self.FUZZY_KEYWORDS:
            keywords = self.FUZZY_KEYWORDS[standard_name]
            for i, norm_h in enumerate(normalized_headers):
                # 检查是否包含关键特征词
                matched_keywords = [kw for kw in keywords if self.normalize_header(kw) in norm_h]
                if matched_keywords:
                    # 排除明显是其他列的情况（如 source_field 匹配到 source_field_type）
                    # 需要区分度足够高
                    if self._check_fuzzy_match_valid(standard_name, norm_h, headers[i]):
                        return ColumnMatch(
                            standard_name=standard_name,
                            actual_name=headers[i],
                            index=i,
                            match_type='fuzzy'
                        )
        
        # 未找到
        return ColumnMatch(
            standard_name=standard_name,
            actual_name='',
            index=-1,
            match_type='not_found'
        )
    
    def _check_fuzzy_match_valid(self, standard_name: str, normalized_header: str, original_header: str) -> bool:
        """
        检查模糊匹配是否有效（避免误匹配）
        
        Args:
            standard_name: 标准列名
            normalized_header: 标准化后的表头
            original_header: 原始表头
            
        Returns:
            是否为有效匹配
        """
        # 排除规则：如果表头包含其他标准列的特征词，可能是其他列
        exclusion_rules = {
            'source_table': ['字段', 'field', 'column'],  # source_table 不应匹配到 source_field
            'source_field': [],
            'target_table': ['字段', 'field', 'column'],
            'target_field': [],
            'source_field_type': ['英文名'],  # type 列不应匹配到名称列
            'target_field_type': ['英文名'],
        }
        
        exclusions = exclusion_rules.get(standard_name, [])
        for excl in exclusions:
            if self.normalize_header(excl) in normalized_header:
                return False
        
        return True
    
    def find_all_columns(
        self, 
        headers: List[str], 
        mapping_type: str = 'field'
    ) -> Dict[str, ColumnMatch]:
        """
        查找所有列的匹配结果
        
        Args:
            headers: 实际表头列表
            mapping_type: 映射类型 ('table' 或 'field')
            
        Returns:
            {标准列名: ColumnMatch} 字典
        """
        headers_dict = self._get_headers(mapping_type)
        results = {}
        
        for standard_name in headers_dict.keys():
            results[standard_name] = self.find_column(headers, standard_name, mapping_type)
        
        return results
    
    def find_sheet(
        self, 
        sheet_names: List[str], 
        sheet_type: str
    ) -> Optional[str]:
        """
        查找指定类型的页签名称
        
        Args:
            sheet_names: 所有页签名称列表
            sheet_type: 页签类型 ('table' 或 'field')
            
        Returns:
            匹配的页签名称，如果未找到返回 None
        """
        alias_list = self.sheet_name_mapping.get(sheet_type, [])
        
        # 完全匹配
        for alias in alias_list:
            if alias in sheet_names:
                return alias
        
        # 模糊匹配
        for name in sheet_names:
            for alias in alias_list:
                normalized_name = self.normalize_header(name)
                normalized_alias = self.normalize_header(alias)
                if normalized_alias in normalized_name or normalized_name in normalized_alias:
                    return name
        
        return None
    
    def get_match_report(
        self, 
        headers: List[str], 
        mapping_type: str = 'field'
    ) -> str:
        """
        生成匹配报告（用于调试）
        
        Args:
            headers: 实际表头列表
            mapping_type: 映射类型
            
        Returns:
            匹配报告字符串
        """
        results = self.find_all_columns(headers, mapping_type)
        
        lines = ["=" * 60]
        lines.append(f"{'标准列名':<25} {'实际列名':<25} {'索引':<5} {'匹配类型'}")
        lines.append("-" * 60)
        
        for standard_name, match in results.items():
            lines.append(
                f"{standard_name:<25} {match.actual_name:<25} "
                f"{match.index:<5} {match.match_type}"
            )
        
        # 检查未匹配的实际列
        matched_indices = {m.index for m in results.values() if m.index >= 0}
        for i, h in enumerate(headers):
            if i not in matched_indices and h:
                lines.append(f"{'(未匹配)':<25} {h:<25} {i:<5} -")
        
        lines.append("=" * 60)
        return "\n".join(lines)


# 便捷函数
def create_header_config(config_path: Optional[str] = None) -> HeaderConfigManager:
    """
    创建表头配置管理器
    
    Args:
        config_path: 外部配置文件路径，可选
        
    Returns:
        HeaderConfigManager 实例
    """
    return HeaderConfigManager(config_path)