"""
长上下文任务：Planner 检索策略 vs Baseline（最近窗口）对比测试。

说明：
- Baseline 仅看最近 3 条历史，容易丢失早期关键上下文。
- Planner 使用关键词相关检索，目标是显著提升命中率。
"""
from __future__ import annotations

from app.planner.orchestrator import TaskPlanner, evaluate_long_context_cases


def test_planner_should_outperform_baseline_on_long_context_cases() -> None:
    """Planner 在长上下文任务上的成功率应高于 baseline。"""
    cases = [
        {
            "goal": "根据合同争议条款给出风险结论",
            "history": [
                "无关聊天1",
                "关键证据: 合同第12条存在争议解决地冲突",
                "无关聊天2",
                "无关聊天3",
                "无关聊天4",
                "无关聊天5",
            ],
            "expected_keywords": ["争议", "合同", "条款"],
        },
        {
            "goal": "结合法务建议给出修订方向",
            "history": [
                "无关聊天A",
                "无关聊天B",
                "关键证据: 法务建议增加违约责任上限",
                "无关聊天C",
                "无关聊天D",
                "无关聊天E",
            ],
            "expected_keywords": ["法务", "违约", "建议"],
        },
        {
            "goal": "总结签署流程里最关键的风险点",
            "history": [
                "关键证据: 签署流程缺少二次确认会导致误签",
                "无关1",
                "无关2",
                "无关3",
                "无关4",
                "无关5",
            ],
            "expected_keywords": ["签署", "风险", "确认"],
        },
    ]

    metrics = evaluate_long_context_cases(
        planner=TaskPlanner(),
        cases=cases,
        baseline_window=3,
    )

    assert metrics["planner_success_rate"] > metrics["baseline_success_rate"]
    assert metrics["planner_success_rate"] - metrics["baseline_success_rate"] >= 0.20

