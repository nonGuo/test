"""
测试用例数据模型
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class TestCase:
    """测试用例"""
    case_id: str
    case_name: str
    category: str  # 用例分类 (功能测试/性能测试/...)
    scene: str  # 测试场景
    priority: str  # 优先级
    
    # 测试步骤
    test_steps: str  # SQL 脚本
    expected_result: str  # 预期结果
    
    # 元数据
    description: str = ""  # 测试要点
    tables: List[str] = field(default_factory=list)  # 涉及表
    pre_condition: str = ""  # 前置条件
    post_condition: str = ""  # 后置条件
    
    # 执行信息
    status: str = "pending"  # pending/passed/failed
    actual_result: str = ""
    executed_by: str = ""
    executed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "case_id": self.case_id,
            "case_name": self.case_name,
            "category": self.category,
            "scene": self.scene,
            "priority": self.priority,
            "description": self.description,
            "tables": ";".join(self.tables),
            "pre_condition": self.pre_condition,
            "test_steps": self.test_steps,
            "expected_result": self.expected_result,
            "post_condition": self.post_condition,
            "status": self.status,
            "actual_result": self.actual_result,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at.isoformat() if self.executed_at else ""
        }


@dataclass
class TestCaseSuite:
    """测试用例集"""
    name: str
    target_table: str
    design_version: str  # 关联的测试设计版本
    cases: List[TestCase] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_case(self, case: TestCase):
        self.cases.append(case)
    
    def get_cases_by_category(self, category: str) -> List[TestCase]:
        """按分类获取用例"""
        return [c for c in self.cases if c.category == category]
    
    def get_cases_by_priority(self, priority: str) -> List[TestCase]:
        """按优先级获取用例"""
        return [c for c in self.cases if c.priority == priority]
    
    def to_excel_data(self) -> List[dict]:
        """转换为 Excel 数据"""
        return [case.to_dict() for case in self.cases]
