"""
Unit tests for app.tools.send_email.
"""

from unittest.mock import patch


class TestSendEmailTool:
    @patch("app.tools.send_email.logger.info")
    def test_logger_masks_recipient_email(self, mock_logger_info) -> None:
        from app.tools.send_email import send_email

        send_email.invoke(
            {
                "to": "user@example.com",
                "subject": "Status Update",
                "body": "hello",
            }
        )

        call_args_str = str(mock_logger_info.call_args)
        assert "user@example.com" not in call_args_str
        assert "u***@example.com" in call_args_str
