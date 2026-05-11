"""
Persistent text memory for long-term conversation notes.

This module stores a compact, human-readable text file per conversation scope
so the assistant can read key facts before replying and refresh the file after
each exchange.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles

logger = logging.getLogger(__name__)


class PersistentMemoryStore:
    """Manage long-term conversation notes as UTF-8 text files."""

    def __init__(self, base_dir: Optional[str | Path] = None, max_prompt_chars: int = 4000):
        self.base_dir = Path(
            base_dir or Path(__file__).resolve().parents[1] / "data" / "ai_memory"
        )
        self.max_prompt_chars = max_prompt_chars

    def _scope_name(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> str:
        if user_id is not None:
            return f"user_{user_id}"
        if group_id is not None:
            return f"group_{group_id}"
        return "global"

    def get_file_path(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Path:
        """Return the text file path for the conversation scope."""
        return self.base_dir / f"{self._scope_name(user_id, group_id)}.txt"

    async def load_text(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> str:
        """Read the persisted text memory for a conversation scope."""
        path = self.get_file_path(user_id, group_id)
        if not path.exists():
            return ""

        async with aiofiles.open(path, mode="r", encoding="utf-8") as file_handle:
            content = await file_handle.read()

        return content.strip()

    async def save_text(
        self,
        content: str,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> Path:
        """Write the persisted text memory for a conversation scope."""
        path = self.get_file_path(user_id, group_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        normalized = content.strip()
        if not normalized:
            normalized = self._default_template()

        if len(normalized) > self.max_prompt_chars:
            normalized = normalized[-self.max_prompt_chars :]

        async with aiofiles.open(path, mode="w", encoding="utf-8") as file_handle:
            await file_handle.write(normalized + "\n")

        logger.debug("长期记忆已保存: %s", path)
        return path

    async def build_prompt_block(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> str:
        """Build a system prompt block containing the persistent memory text."""
        memory_text = await self.load_text(user_id=user_id, group_id=group_id)

        if not memory_text:
            memory_text = self._default_template()

        if len(memory_text) > self.max_prompt_chars:
            memory_text = memory_text[-self.max_prompt_chars :]

        scope_name = self._scope_name(user_id, group_id)
        return (
            "你必须优先参考下面的长期记忆文件。\n"
            "如果记忆中存在与当前对话相关的偏好、历史事项、账单或提醒，请延续使用。\n"
            f"【长期记忆开始 | scope={scope_name}】\n"
            f"{memory_text}\n"
            "【长期记忆结束】"
        )

    async def update_from_exchange(
        self,
        llm_client,
        user_text: str,
        assistant_text: str,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> str:
        """Use the LLM to refresh the persistent memory text from one exchange."""
        existing_text = await self.load_text(user_id=user_id, group_id=group_id)
        if not existing_text:
            existing_text = self._default_template()

        system_prompt = (
            "你是一个长期记忆整理器。你的任务是把最新对话提炼成适合长期保存的中文文本。\n"
            "只保留稳定、长期有用的信息，例如：用户偏好、身份信息、长期目标、记账习惯、提醒事项、待办。\n"
            "不要记录无意义的寒暄，不要复制整段聊天，不要输出解释。\n"
            "输出必须是可直接保存为纯文本的内容，尽量短，使用分点结构。"
        )

        user_prompt = (
            f"当前时间: {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n\n"
            f"现有长期记忆:\n{existing_text}\n\n"
            f"最新对话:\n用户: {user_text}\n助手: {assistant_text}\n\n"
            "请输出更新后的长期记忆文本。"
        )

        updated_text = await llm_client.call(
            "更新长期记忆",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        final_text = self._sanitize_text(updated_text, fallback=existing_text)
        await self.save_text(final_text, user_id=user_id, group_id=group_id)
        return final_text

    def _sanitize_text(self, text: str, fallback: str) -> str:
        cleaned = text.strip()
        if not cleaned:
            return fallback.strip() or self._default_template()

        if len(cleaned) > self.max_prompt_chars:
            cleaned = cleaned[-self.max_prompt_chars :]

        return cleaned

    def _default_template(self) -> str:
        return (
            "# 长期记忆\n"
            "更新时间: 暂无\n\n"
            "## 关键事实\n"
            "- 暂无\n\n"
            "## 偏好\n"
            "- 暂无\n\n"
            "## 记账/财务\n"
            "- 暂无\n\n"
            "## 提醒/待办\n"
            "- 暂无\n"
        )