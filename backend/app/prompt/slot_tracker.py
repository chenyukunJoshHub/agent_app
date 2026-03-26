"""Slot Content Tracker - 跟踪每个 Slot 的内容和 Token 计数.

这个模块提供 SlotContentTracker 类，用于在构建 prompt 时
收集每个 Slot 的实际内容和对应的 token 消耗。

基于 Prompt v20 §1.2 十大子模块与 Context Window 分区
"""
from dataclasses import dataclass, field
from typing import Any

from app.utils.token import count_tokens


@dataclass
class SlotContent:
    """单个 Slot 的内容和 Token 计数"""

    # Slot 名称
    name: str
    # Slot 显示名称（中文）
    display_name: str
    # Slot 内容
    content: str
    # Token 计数
    tokens: int = 0
    # 是否启用
    enabled: bool = True

    def __post_init__(self):
        """计算 token 数量"""
        if self.tokens == 0 and self.content:
            self.tokens = count_tokens(self.content)


@dataclass
class SlotSnapshot:
    """Slot 快照 - 包含所有 Slot 的状态"""

    # 所有 Slot 的内容
    slots: dict[str, SlotContent] = field(default_factory=dict)
    # 总 token 数
    total_tokens: int = 0
    # 时间戳
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式（用于 SSE 事件）"""
        return {
            "slots": [
                {
                    "name": slot.name,
                    "display_name": slot.display_name,
                    "content": slot.content,
                    "tokens": slot.tokens,
                    "enabled": slot.enabled,
                }
                for slot in self.slots.values()
            ],
            "total_tokens": self.total_tokens,
            "timestamp": self.timestamp,
        }


class SlotContentTracker:
    """Slot 内容跟踪器

    职责：
    1. 收集每个 Slot 的内容
    2. 计算每个 Slot 的 token 消耗
    3. 生成 Slot 快照（用于 SSE 推送）

    使用方式：
        tracker = SlotContentTracker()

        # 添加 Slot 内容
        tracker.add_slot("system", "系统提示词内容", "系统提示词")
        tracker.add_slot("active_skill", "", "活跃技能")  # 空 content 表示未激活

        # 生成快照
        snapshot = tracker.build_snapshot()
    """

    # Slot 显示名称映射
    SLOT_DISPLAY_NAMES: dict[str, str] = {
        "system": "系统提示词",
        "active_skill": "活跃技能",
        "few_shot": "静态示例",
        "rag": "背景知识",
        "episodic": "用户画像",
        "procedural": "程序记忆",
        "tools": "工具定义",
        "history": "对话历史",
        "output_format": "输出格式",
        "user_input": "用户输入",
        "skill_registry": "Skill 注册表",
        "skill_protocol": "Skill 协议",
    }

    def __init__(self) -> None:
        """初始化跟踪器"""
        self._slots: dict[str, SlotContent] = {}

    def add_slot(
        self,
        name: str,
        content: str,
        display_name: str | None = None,
        enabled: bool = True,
    ) -> None:
        """添加或更新一个 Slot

        Args:
            name: Slot 名称（如 "system", "active_skill"）
            content: Slot 内容
            display_name: 显示名称（可选，默认从 SLOT_DISPLAY_NAMES 获取）
            enabled: 是否启用
        """
        if display_name is None:
            display_name = self.SLOT_DISPLAY_NAMES.get(name, name)

        slot = SlotContent(
            name=name,
            display_name=display_name,
            content=content,
            enabled=enabled,
        )
        self._slots[name] = slot

    def update_slot(self, name: str, content: str) -> None:
        """更新现有 Slot 的内容

        Args:
            name: Slot 名称
            content: 新内容
        """
        if name in self._slots:
            self._slots[name].content = content
            # 重新计算 token
            self._slots[name].tokens = count_tokens(content)
            # 如果内容非空，启用该 Slot
            self._slots[name].enabled = bool(content)

    def get_slot(self, name: str) -> SlotContent | None:
        """获取指定 Slot

        Args:
            name: Slot 名称

        Returns:
            SlotContent 或 None
        """
        return self._slots.get(name)

    def get_total_tokens(self) -> int:
        """计算所有启用的 Slot 的总 token 数

        Returns:
            int: 总 token 数
        """
        return sum(slot.tokens for slot in self._slots.values() if slot.enabled)

    def build_snapshot(self) -> SlotSnapshot:
        """构建 Slot 快照

        Returns:
            SlotSnapshot: 包含所有 Slot 状态的快照
        """
        import time

        return SlotSnapshot(
            slots=dict(self._slots),
            total_tokens=self.get_total_tokens(),
            timestamp=time.time(),
        )

    def clear(self) -> None:
        """清空所有 Slot"""
        self._slots.clear()

    def get_summary(self) -> dict[str, Any]:
        """获取摘要信息（用于调试）

        Returns:
            dict: 摘要信息
        """
        return {
            "total_slots": len(self._slots),
            "enabled_slots": sum(1 for s in self._slots.values() if s.enabled),
            "total_tokens": self.get_total_tokens(),
            "slots": {
                name: {
                    "tokens": slot.tokens,
                    "enabled": slot.enabled,
                    "content_preview": slot.content[:100] if slot.content else "",
                }
                for name, slot in self._slots.items()
            },
        }


__all__ = [
    "SlotContent",
    "SlotSnapshot",
    "SlotContentTracker",
]
