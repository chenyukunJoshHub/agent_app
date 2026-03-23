"""Unit tests for app.tools.send_email.

These tests verify the send_email tool functionality.
"""
import json

import pytest


class TestSendEmailTool:
    """Test send_email tool."""

    def test_tool_has_correct_metadata(self) -> None:
        """Test that tool has proper metadata."""
        from app.tools.send_email import send_email

        assert send_email.name == "send_email"
        assert send_email.description is not None
        assert "发送邮件" in send_email.description
        # Should include HIL warning
        assert "HIL" in send_email.description or "人工介入" in send_email.description
        # Should include usage guidance
        assert "适用" in send_email.description or "不适用" in send_email.description

    def test_tool_args_schema(self) -> None:
        """Test that tool has correct args schema."""
        from app.tools.send_email import send_email

        schema = send_email.args_schema
        assert schema is not None
        # Should have required arguments
        assert "to" in schema.model_fields
        assert "subject" in schema.model_fields
        assert "body" in schema.model_fields

    def test_send_email_basic_execution(self) -> None:
        """Test send_email with valid parameters."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "Test Subject",
            "body": "Test Body"
        })

        # Should return JSON string
        assert isinstance(result, str)
        data = json.loads(result)

        # Verify response structure
        assert data["success"] is True
        assert "email_id" in data
        assert data["to"] == "test@example.com"
        assert data["subject"] == "Test Subject"
        assert "sent_at" in data
        assert data["note"] == "这是模拟发送，实际邮件未发出"

    def test_send_email_hil_warning_in_description(self) -> None:
        """Test that send_email description contains HIL warning."""
        from app.tools.send_email import send_email

        desc = send_email.description
        assert "⚠️" in desc or "HIL" in desc or "人工介入" in desc
        assert "不可逆" in desc or "无法撤回" in desc

    def test_send_email_returns_valid_json(self) -> None:
        """Test that send_email returns valid JSON."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "recipient@example.com",
            "subject": "Test",
            "body": "Body"
        })

        # Should be valid JSON
        data = json.loads(result)
        assert isinstance(data, dict)

        # Verify all required fields
        required_fields = ["success", "message", "email_id", "to", "subject", "sent_at", "note"]
        for field in required_fields:
            assert field in data

    def test_send_email_generates_unique_id(self) -> None:
        """Test that each send_email call generates a unique ID."""
        from app.tools.send_email import send_email
        import time

        result1 = send_email.invoke({
            "to": "test@example.com",
            "subject": "Test 1",
            "body": "Body 1"
        })

        # Small delay to ensure different timestamp
        time.sleep(0.1)

        result2 = send_email.invoke({
            "to": "test@example.com",
            "subject": "Test 2",
            "body": "Body 2"
        })

        data1 = json.loads(result1)
        data2 = json.loads(result2)

        # Email IDs should be different
        assert data1["email_id"] != data2["email_id"]

    def test_send_email_with_special_characters(self) -> None:
        """Test send_email handles special characters in content."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "测试主题: 重要通知!",
            "body": "Body with 特殊字符: 🎉🚀"
        })

        data = json.loads(result)
        assert data["success"] is True
        # Verify special characters are preserved in subject
        assert "测试主题" in data["subject"]

    def test_send_email_timestamp_format(self) -> None:
        """Test that send_email returns valid ISO timestamp."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "Test",
            "body": "Body"
        })

        data = json.loads(result)
        timestamp = data["sent_at"]

        # Should be valid ISO format timestamp
        assert "T" in timestamp
        assert ":" in timestamp

    def test_send_email_allows_long_body(self) -> None:
        """Test send_email handles long email body."""
        from app.tools.send_email import send_email

        long_body = "This is a long email body. " * 100

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "Long Body Test",
            "body": long_body
        })

        data = json.loads(result)
        assert data["success"] is True

    def test_send_email_with_empty_subject(self) -> None:
        """Test send_email accepts empty subject."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "",
            "body": "Body"
        })

        data = json.loads(result)
        assert data["success"] is True
        assert data["subject"] == ""

    def test_send_email_with_empty_body(self) -> None:
        """Test send_email accepts empty body."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "Test",
            "body": ""
        })

        data = json.loads(result)
        assert data["success"] is True


class TestSendEmailEdgeCases:
    """Test send_email tool edge cases."""

    def test_send_email_description_clarity(self) -> None:
        """Test that tool description is clear and helpful."""
        from app.tools.send_email import send_email

        desc = send_email.description.lower()
        # Should mention what it's for
        assert any(keyword in desc for keyword in ["发送", "邮件", "email"])
        # Should mention it's a mock
        assert "模拟" in desc or "mock" in desc
        # Should mention HIL
        assert "hil" in desc or "人工介入" in desc or "不可逆" in desc

    def test_send_email_returns_string_type(self) -> None:
        """Test that send_email always returns a string."""
        from app.tools.send_email import send_email

        result = send_email.invoke({
            "to": "test@example.com",
            "subject": "Test",
            "body": "Body"
        })

        assert isinstance(result, str)

    def test_send_email_preserves_all_parameters(self) -> None:
        """Test that send_email preserves all input parameters."""
        from app.tools.send_email import send_email

        test_to = "recipient@example.com"
        test_subject = "Important Update"
        test_body = "Please review the attached document."

        result = send_email.invoke({
            "to": test_to,
            "subject": test_subject,
            "body": test_body
        })

        data = json.loads(result)
        assert data["to"] == test_to
        assert data["subject"] == test_subject
