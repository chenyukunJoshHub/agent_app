"""
Mock email sending tool for HIL demonstration.

This tool simulates sending emails without actually sending them.
Used to demonstrate Human-in-the-Loop (HIL) intervention flow.
"""
from datetime import UTC, datetime

from langchain_core.tools import tool
from loguru import logger


def _mask_email(value: str) -> str:
    if "@" not in value:
        return "***"
    local, _, domain = value.partition("@")
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """
    发送邮件给指定收件人。

    ⚠️ HIL 警告：此工具为不可逆操作，邮件发出后无法撤回。
                使用此工具时会触发人工介入确认流程。

    适用场景：
    - 发送报告给团队成员
    - 通知客户重要信息
    - 发送合同签署提醒
    - 发送数据分析结果

    不适用场景：
    - 需要立即执行的紧急通知
    - 批量邮件发送（请使用其他工具）
    - 附件发送（此工具仅支持纯文本）

    Args:
        to: 收件人邮箱地址
        subject: 邮件主题
        body: 邮件正文内容（纯文本）

    Returns:
        str: 发送结果，包含时间戳和模拟邮件ID
    """
    logger.info("Mock email to {} (subject chars={})", _mask_email(to), len(subject))

    # Simulate email sending
    timestamp = datetime.now(UTC).isoformat()
    mock_email_id = f"MSG-{timestamp.replace('-', '').replace(':', '').replace('.', '')[:16]}"

    result = {
        "success": True,
        "message": "邮件已发送（模拟）",
        "email_id": mock_email_id,
        "to": to,
        "subject": subject,
        "sent_at": timestamp,
        "note": "这是模拟发送，实际邮件未发出",
    }

    import json
    return json.dumps(result, ensure_ascii=False)


# Tool list for LangGraph
__all__ = ["send_email"]
