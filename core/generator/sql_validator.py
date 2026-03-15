"""
SQL 质量验证器

验证生成的 SQL 质量，提供优化建议：
- 语法正确性检查
- 性能问题检测
- 完整性验证
- 安全性检查
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import re


@dataclass
class SQLValidationResult:
    """SQL 验证结果"""
    sql: str
    is_valid: bool
    score: float  # 0-100
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)


class SQLValidator:
    """SQL 质量验证器"""

    # SQL 语法关键字
    SQL_KEYWORDS = {
        "SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY",
        "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON",
        "UNION", "INTERSECT", "EXCEPT",
        "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER",
        "CASE", "WHEN", "THEN", "ELSE", "END",
        "AS", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE"
    }

    # 性能反模式
    PERFORMANCE_ANTI_PATTERNS = [
        (r"SELECT\s+\*", "避免 SELECT *，明确指定需要的列"),
        (r"\bWHERE\b.*\bOR\b.*\b=\b", "OR 条件可能导致索引失效"),
        (r"LIKE\s*['\"]%", "前缀模糊查询可能导致全表扫描"),
        (r"NOT\s+IN\s*\(", "NOT IN 可能导致性能问题，考虑使用 NOT EXISTS"),
        (r"IS\s+NOT\s+NULL", "IS NOT NULL 可能影响索引使用"),
        (r"YEAR\s*\(\s*\w+\s*\)", "对字段使用函数可能导致索引失效"),
        (r"UPPER\s*\(\s*\w+\s*\)", "对字段使用函数可能导致索引失效"),
        (r"LOWER\s*\(\s*\w+\s*\)", "对字段使用函数可能导致索引失效"),
        (r"SUBSTRING\s*\(\s*\w+", "对字段使用函数可能导致索引失效"),
        (r"TRIM\s*\(\s*\w+", "对字段使用函数可能导致索引失效"),
    ]

    # 安全反模式
    SECURITY_ANTI_PATTERNS = [
        (r"--\s*$", "SQL 注释可能隐藏恶意代码"),
        (r";\s*DROP\s+", "检测到 DROP 操作，存在安全风险"),
        (r";\s*DELETE\s+", "检测到 DELETE 操作，存在安全风险"),
        (r";\s*UPDATE\s+", "检测到 UPDATE 操作，存在安全风险"),
        (r"EXEC\s+", "检测到 EXEC 调用，存在安全风险"),
        (r"EXECUTE\s+", "检测到 EXECUTE 调用，存在安全风险"),
    ]

    def __init__(self):
        pass

    def validate(self, sql: str) -> SQLValidationResult:
        """
        验证 SQL 质量

        Args:
            sql: SQL 脚本

        Returns:
            SQLValidationResult 对象
        """
        issues = []
        warnings = []
        suggestions = []
        
        # 1. 基础语法检查
        syntax_valid, syntax_issues = self._check_syntax(sql)
        if not syntax_valid:
            issues.extend(syntax_issues)
        
        # 2. 完整性检查
        completeness_valid, completeness_issues = self._check_completeness(sql)
        if not completeness_valid:
            issues.extend(completeness_issues)
        
        # 3. 性能检查
        perf_warnings, perf_suggestions = self._check_performance(sql)
        warnings.extend(perf_warnings)
        suggestions.extend(perf_suggestions)
        
        # 4. 安全检查
        security_issues = self._check_security(sql)
        issues.extend(security_issues)
        
        # 5. 可读性检查
        readability_suggestions = self._check_readability(sql)
        suggestions.extend(readability_suggestions)
        
        # 6. 计算指标
        metrics = self._calculate_metrics(sql)
        
        # 7. 计算总分
        score = self._calculate_score(issues, warnings, metrics)
        
        return SQLValidationResult(
            sql=sql,
            is_valid=len(issues) == 0,
            score=score,
            issues=issues,
            warnings=warnings,
            suggestions=suggestions,
            metrics=metrics
        )

    def _check_syntax(self, sql: str) -> Tuple[bool, List[str]]:
        """检查语法正确性"""
        issues = []
        sql_upper = sql.upper()
        
        # 检查是否有 SELECT
        if "SELECT" not in sql_upper:
            issues.append("缺少 SELECT 关键字")
        
        # 检查是否有 FROM
        if "FROM" not in sql_upper:
            issues.append("缺少 FROM 子句")
        
        # 检查括号匹配
        open_parens = sql.count("(")
        close_parens = sql.count(")")
        if open_parens != close_parens:
            issues.append(f"括号不匹配：{open_parens} 个左括号，{close_parens} 个右括号")
        
        # 检查 CASE WHEN 配对
        case_count = sql_upper.count("CASE")
        end_count = sql_upper.count("END")
        if case_count > end_count:
            issues.append("CASE WHEN 语句缺少 END")
        
        # 检查字符串引号匹配
        single_quotes = sql.count("'") - sql.count("\\'")
        if single_quotes % 2 != 0:
            issues.append("字符串引号不匹配")
        
        return len(issues) == 0, issues

    def _check_completeness(self, sql: str) -> Tuple[bool, List[str]]:
        """检查完整性"""
        issues = []
        
        # 检查是否有注释说明
        if "--" not in sql and "/*" not in sql:
            issues.append("缺少 SQL 注释说明")
        
        # 检查是否有预期结果说明
        if "预期" not in sql and "expected" not in sql.lower():
            issues.append("缺少预期结果说明")
        
        # 检查是否有测试目的说明
        if "测试" not in sql and "test" not in sql.lower():
            issues.append("缺少测试目的说明")
        
        return len(issues) == 0, issues

    def _check_performance(self, sql: str) -> Tuple[List[str], List[str]]:
        """检查性能问题"""
        warnings = []
        suggestions = []
        
        for pattern, message in self.PERFORMANCE_ANTI_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                warnings.append(f"性能警告：{message}")
        
        # 检查是否有限制
        sql_upper = sql.upper()
        if "LIMIT" not in sql_upper and "TOP" not in sql_upper and "ROWNUM" not in sql_upper:
            if "SELECT" in sql_upper:
                suggestions.append("建议添加 LIMIT 限制返回行数")
        
        # 检查是否有索引提示
        if "JOIN" in sql_upper:
            suggestions.append("确保 JOIN 条件字段有索引")
        
        return warnings, suggestions

    def _check_security(self, sql: str) -> List[str]:
        """检查安全问题"""
        issues = []
        
        for pattern, message in self.SECURITY_ANTI_PATTERNS:
            if re.search(pattern, sql, re.IGNORECASE):
                issues.append(f"安全警告：{message}")
        
        return issues

    def _check_readability(self, sql: str) -> List[str]:
        """检查可读性"""
        suggestions = []
        
        # 检查是否单行过长
        lines = sql.split("\n")
        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                suggestions.append(f"第 {i} 行超过 120 字符，建议换行")
                break
        
        # 检查是否使用了别名
        if "JOIN" in sql.upper() and " AS " not in sql.upper():
            suggestions.append("建议为表使用别名提高可读性")
        
        # 检查格式化
        if sql.count("\n") < 2:
            suggestions.append("建议格式化 SQL，每个子句独占一行")
        
        return suggestions

    def _calculate_metrics(self, sql: str) -> Dict:
        """计算 SQL 指标"""
        sql_upper = sql.upper()
        
        return {
            "length": len(sql),
            "line_count": sql.count("\n") + 1,
            "select_count": sql_upper.count("SELECT"),
            "join_count": sql_upper.count("JOIN"),
            "where_count": sql_upper.count("WHERE"),
            "group_by_count": sql_upper.count("GROUP BY"),
            "order_by_count": sql_upper.count("ORDER BY"),
            "case_when_count": sql_upper.count("CASE"),
            "subquery_count": sql_upper.count("SELECT") - 1 if sql_upper.count("SELECT") > 1 else 0,
            "comment_count": sql.count("--") + sql.count("/*"),
        }

    def _calculate_score(self, issues: List[str], warnings: List[str], metrics: Dict) -> float:
        """计算质量分数"""
        score = 100.0
        
        # 问题扣分 (每个 -15 分)
        score -= len(issues) * 15
        
        # 警告扣分 (每个 -5 分)
        score -= len(warnings) * 5
        
        # 指标评分
        if metrics.get("comment_count", 0) >= 2:
            score += 10  # 有注释加分
        if metrics.get("line_count", 0) >= 3:
            score += 5  # 格式化加分
        
        # 确保分数在 0-100 之间
        return max(0.0, min(100.0, score))

    def validate_batch(self, sql_list: List[str]) -> List[SQLValidationResult]:
        """批量验证 SQL"""
        return [self.validate(sql) for sql in sql_list]

    def get_validation_report(self, results: List[SQLValidationResult]) -> str:
        """生成验证报告"""
        if not results:
            return "没有 SQL 需要验证"
        
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        avg_score = sum(r.score for r in results) / total
        
        report = []
        report.append("=" * 60)
        report.append("SQL 质量验证报告")
        report.append("=" * 60)
        report.append(f"总 SQL 数：{total}")
        report.append(f"有效 SQL 数：{valid}")
        report.append(f"平均分数：{avg_score:.1f}")
        report.append("")
        
        # 低分 SQL 详情
        low_score_results = [r for r in results if r.score < 60]
        if low_score_results:
            report.append("-" * 60)
            report.append("需要优化的 SQL (分数 < 60):")
            report.append("-" * 60)
            for i, result in enumerate(low_score_results[:5], 1):
                report.append(f"\n[SQL {i}] 分数：{result.score:.1f}")
                if result.issues:
                    report.append("  问题:")
                    for issue in result.issues:
                        report.append(f"    - {issue}")
                if result.warnings:
                    report.append("  警告:")
                    for warning in result.warnings:
                        report.append(f"    - {warning}")
                if result.suggestions:
                    report.append("  建议:")
                    for suggestion in result.suggestions:
                        report.append(f"    - {suggestion}")
        
        return "\n".join(report)


class SQLOptimizer:
    """SQL 优化器"""

    def optimize(self, sql: str) -> str:
        """
        优化 SQL

        Args:
            sql: 原始 SQL

        Returns:
            优化后的 SQL
        """
        optimized = sql
        
        # 1. 替换 SELECT *
        optimized = re.sub(
            r"SELECT\s+\*\s+FROM",
            r"SELECT /* 请指定具体列 */ * FROM",
            optimized,
            flags=re.IGNORECASE
        )
        
        # 2. 添加 LIMIT (如果没有)
        if "LIMIT" not in optimized.upper() and "SELECT" in optimized.upper():
            optimized = optimized.rstrip(";") + "\nLIMIT 1000;"
        
        # 3. 格式化
        optimized = self._format_sql(optimized)
        
        return optimized

    def _format_sql(self, sql: str) -> str:
        """格式化 SQL"""
        # 简单实现：确保每个子句独占一行
        keywords = ["SELECT", "FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY", "LIMIT", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN"]
        
        formatted = sql
        for kw in keywords:
            pattern = r"\s+" + kw + r"\s+"
            formatted = re.sub(pattern, f"\n{kw} ", formatted, flags=re.IGNORECASE)
        
        return formatted.strip()
