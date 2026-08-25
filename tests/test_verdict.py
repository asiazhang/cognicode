"""判卷五类结果分类的单元测试。

类别语义（#6 锁定的五类互斥）：
- success: 判卷通过（F2P 通过且 P2P 无回归 / 位置匹配 / 探测回路跑通）
- fail_incorrect: 跑完但未通过（含破坏既有行为）
- fail_budget: 触及轮次或时间上限
- fail_env: harness 侧环境故障（worktree 损坏、agent 进程崩溃、网络故障）

前三类计入统计；fail_env 剔除并重跑。
"""

import pytest

from cognicode.verdict import (
    OUTCOME_CATEGORIES,
    classify_verdict,
    is_counted,
)


class TestClassifyVerdict:
    """一次任务运行的判卷归类。"""

    def test_success(self):
        assert classify_verdict("success") == "success"

    def test_fail_incorrect(self):
        assert classify_verdict("fail_incorrect") == "fail_incorrect"

    def test_fail_budget(self):
        assert classify_verdict("fail_budget") == "fail_budget"

    def test_fail_env(self):
        assert classify_verdict("fail_env") == "fail_env"

    def test_unknown_category_rejected(self):
        with pytest.raises(ValueError):
            classify_verdict("pass")

    def test_outcome_categories_fixed_order(self):
        # 五类互斥，顺序即文档
        assert OUTCOME_CATEGORIES == [
            "success",
            "fail_incorrect",
            "fail_budget",
            "fail_env",
        ]


class TestIsCounted:
    """前三类计入统计，fail_env 剔除。"""

    def test_success_counted(self):
        assert is_counted("success") is True

    def test_fail_incorrect_counted(self):
        assert is_counted("fail_incorrect") is True

    def test_fail_budget_counted(self):
        assert is_counted("fail_budget") is True

    def test_fail_env_not_counted(self):
        assert is_counted("fail_env") is False
