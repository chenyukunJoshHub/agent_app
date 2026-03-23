"""单元测试：内部操作 Prompt

测试 internal.py 中的内部系统 Prompt 模板。
"""

import pytest
from app.prompt.internal import (
    COMPRESSOR_PROMPT,
    HIL_CONFIRM_TEMPLATE,
    ERROR_RECOVERY_RULES,
    COMPRESSOR_FEW_SHOT,
)


class TestCompressorPrompt:
    """测试压缩器 Prompt"""

    def test_compressor_prompt_exists(self):
        """验证 COMPRESSOR_PROMPT 非空"""
        assert COMPRESSOR_PROMPT
        assert len(COMPRESSOR_PROMPT) > 0

    def test_compressor_prompt_has_placeholder(self):
        """验证有 {messages} 占位符"""
        assert "{messages}" in COMPRESSOR_PROMPT

    def test_compressor_prompt_format(self):
        """验证可以正确格式化"""
        messages = "用户: 你好\n助手: 你好！"
        result = COMPRESSOR_PROMPT.format(messages=messages)
        assert "用户: 你好" in result
        assert "助手: 你好！" in result

    def test_compressor_prompt_contains_instructions(self):
        """验证包含压缩指令"""
        assert "必须保留" in COMPRESSOR_PROMPT
        assert "可以省略" in COMPRESSOR_PROMPT
        assert "核心任务目标" in COMPRESSOR_PROMPT


class TestHILConfirmTemplate:
    """测试 HIL 确认模板"""

    def test_hil_confirm_template_exists(self):
        """验证模板非空"""
        assert HIL_CONFIRM_TEMPLATE
        assert len(HIL_CONFIRM_TEMPLATE) > 0

    def test_hil_confirm_template_has_placeholders(self):
        """验证有所有必需的占位符"""
        assert "{action_type}" in HIL_CONFIRM_TEMPLATE
        assert "{scope_description}" in HIL_CONFIRM_TEMPLATE
        assert "{action_detail}" in HIL_CONFIRM_TEMPLATE
        assert "{expected_result}" in HIL_CONFIRM_TEMPLATE

    def test_hil_confirm_template_format(self):
        """验证可以正确格式化"""
        result = HIL_CONFIRM_TEMPLATE.format(
            action_type="发送邮件",
            scope_description="23 位签署方",
            action_detail="发送逾期提醒",
            expected_result="签署方收到提醒"
        )

        assert "发送邮件" in result
        assert "23 位签署方" in result
        assert "发送逾期提醒" in result
        assert "签署方收到提醒" in result

    def test_hil_confirm_template_has_warning(self):
        """验证包含警告符号"""
        assert "⚠️" in HIL_CONFIRM_TEMPLATE
        assert "[✅ 确认执行]" in HIL_CONFIRM_TEMPLATE
        assert "[❌ 取消操作]" in HIL_CONFIRM_TEMPLATE


class TestErrorRecoveryRules:
    """测试错误恢复规则"""

    def test_error_recovery_rules_exist(self):
        """验证规则非空"""
        assert ERROR_RECOVERY_RULES
        assert len(ERROR_RECOVERY_RULES) > 0

    def test_error_recovery_rules_content(self):
        """验证包含关键规则"""
        assert "重试" in ERROR_RECOVERY_RULES
        assert "2 次" in ERROR_RECOVERY_RULES
        assert "死循环" in ERROR_RECOVERY_RULES


class TestCompressorFewShot:
    """测试压缩器 Few-shot 示例"""

    def test_compressor_few_shot_exists(self):
        """验证非空"""
        assert COMPRESSOR_FEW_SHOT
        assert len(COMPRESSOR_FEW_SHOT) > 0

    def test_compressor_few_shot_has_examples(self):
        """验证包含示例"""
        assert "示例 1" in COMPRESSOR_FEW_SHOT
        assert "示例 2" in COMPRESSOR_FEW_SHOT

    def test_compressor_few_shot_shows_format(self):
        """验证展示输入输出格式"""
        assert "输入：" in COMPRESSOR_FEW_SHOT
        assert "输出：" in COMPRESSOR_FEW_SHOT
