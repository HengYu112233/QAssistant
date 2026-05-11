"""
Message processor module - the central orchestrator for message handling.
Routes QQ messages through LLM and sends responses back.
"""

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from core.llm_client import LLMClient
from core.bot_client import BotClient
from core.database import DatabaseManager
from agent.memory import ConversationMemory
from agent.persistent_memory import PersistentMemoryStore

logger = logging.getLogger(__name__)


class MessageProcessor:
    """
    消息处理中枢。
    
    Flow:
    1. 从机器人接收消息
    2. 检查对话记忆
    3. 调用大模型生成回复
    4. 将回复发送回 QQ

    课程概念映射：
    - RAG：从短期对话记忆与长期记忆文件中检索上下文，再拼入提示词。
    - MCP：把数据库写入、提醒发送、QQ 回复等外部能力当成可调用服务。
    - Subagent：把长期记忆更新放到后台任务中异步执行，避免阻塞主回复链路。
    """

    def __init__(
        self,
        llm_client: LLMClient,
        bot_client: BotClient,
        memory: ConversationMemory,
        database: Optional[DatabaseManager] = None,
        persistent_memory: Optional[PersistentMemoryStore] = None,
        enable_memory: bool = True,
        memory_context_window: int = 10,
    ):
        """
        Initialize message processor.

        Args:
            llm_client: LLM client instance.
            bot_client: Bot client instance.
            memory: Conversation memory instance.
            enable_memory: Enable conversation history for context.
            memory_context_window: Number of historical messages to include.
        """
        self.llm_client = llm_client
        self.bot_client = bot_client
        self.memory = memory
        self.database = database
        self.persistent_memory = persistent_memory or PersistentMemoryStore()
        self.enable_memory = enable_memory
        self.memory_context_window = memory_context_window

        logger.debug("MessageProcessor 已初始化")

    @staticmethod
    def _clean_memo_content(raw_text: str) -> str:
        cleaned = raw_text.strip()
        cleaned = re.sub(r"^(我今天|今天|我|刚刚|刚才)\s*", "", cleaned)
        cleaned = re.sub(r"^(记账|记一笔|记下)\s*", "", cleaned)
        cleaned = cleaned.strip(" ，。:：-")
        return cleaned or "日常支出"

    @staticmethod
    def _extract_accounting_entry(user_text: str) -> Optional[tuple[float, str]]:
        """Extract a simple accounting entry from free-form text."""
        patterns = [
            re.compile(r"^(?P<content>.+?)花了(?P<amount>\d+(?:\.\d+)?)\s*元$"),
            re.compile(r"^(?:记账|记一笔|记下)?\s*(?P<amount>\d+(?:\.\d+)?)\s*元(?P<content>.+)$"),
            re.compile(r"^(?P<content>.+?)[,，\s]*(?P<amount>\d+(?:\.\d+)?)\s*元$"),
        ]

        normalized = user_text.strip()
        for pattern in patterns:
            match = pattern.match(normalized)
            if not match:
                continue

            amount_text = match.group("amount")
            content_text = match.groupdict().get("content") or "日常支出"
            try:
                amount = float(amount_text)
            except ValueError:
                continue

            return amount, MessageProcessor._clean_memo_content(content_text)

        return None

    @staticmethod
    def _extract_spending_query_keyword(user_text: str) -> Optional[str]:
        """Extract a spending keyword for queries like '今天吃饭花了多少钱'."""
        patterns = [
            re.compile(r"^(?P<keyword>.+?)花了多少钱$"),
            re.compile(r"^(?P<keyword>.+?)多少钱$"),
            re.compile(r"^(?P<keyword>.+?)总共花了多少(?:钱|元)$"),
        ]

        normalized = user_text.strip()
        for pattern in patterns:
            match = pattern.match(normalized)
            if match:
                keyword = match.group("keyword").strip()
                keyword = re.sub(r"^(我今天|今天|我|这几天|这周|这个月)\s*", "", keyword)
                return keyword or None

        return None

    async def _handle_accounting_query(self, user_id: int, user_text: str) -> Optional[str]:
        if self.database is None:
            return None

        keyword = self._extract_spending_query_keyword(user_text)
        if keyword is None:
            return None

        total_amount = await self.database.sum_memos(
            user_id=user_id,
            memo_type="accounting",
            keyword=keyword,
            on_date=datetime.now(timezone.utc),
        )

        if total_amount <= 0:
            return f"今天没有记录到“{keyword}”的支出。"

        amount_text = f"{total_amount:.2f}".rstrip("0").rstrip(".")
        return f"你今天“{keyword}”共花了 {amount_text} 元。"

    async def _record_accounting_entry(self, user_id: int, user_text: str) -> Optional[tuple[float, str]]:
        if self.database is None:
            return None

        parsed_entry = self._extract_accounting_entry(user_text)
        if parsed_entry is None:
            return None

        amount, content = parsed_entry
        await self.database.add_memo(
            user_id=user_id,
            memo_type="accounting",
            content=content,
            amount=amount,
            timestamp=datetime.now(timezone.utc),
        )
        return amount, content

    def _spawn_background_task(self, coroutine, description: str) -> None:
        """Run a background task and log failures without blocking the main reply flow."""
        task = asyncio.create_task(coroutine)

        def _on_done(finished_task: asyncio.Task) -> None:
            try:
                exception = finished_task.exception()
            except asyncio.CancelledError:
                logger.debug("后台任务已取消: %s", description)
                return
            except Exception as exc:
                logger.error("读取后台任务结果失败: %s, 错误=%s", description, exc)
                return

            if exception is not None:
                logger.error("后台任务失败: %s, 类型=%s, 错误=%s", description, type(exception).__name__, exception)

        task.add_done_callback(_on_done)

    async def _build_rag_context_messages(
        self,
        user_id: Optional[int],
        group_id: Optional[int],
    ) -> list[dict[str, str]]:
        """Build the retrieval-augmented context from short-term conversation memory."""
        if not self.enable_memory:
            return []

        return self.memory.get_context_for_llm(
            user_id=user_id,
            group_id=group_id,
            context_window=self.memory_context_window,
        )

    async def _build_mcp_system_message(
        self,
        user_id: Optional[int],
        group_id: Optional[int],
    ) -> dict[str, str]:
        """Build the system message that binds the LLM to external capabilities and durable memory."""
        system_prompt = self.llm_client.system_prompt
        persistent_block = await self.persistent_memory.build_prompt_block(
            user_id=user_id,
            group_id=group_id,
        )

        return {
            "role": "system",
            "content": f"{system_prompt}\n\n{persistent_block}",
        }

    async def _build_llm_messages(
        self,
        user_id: Optional[int],
        group_id: Optional[int],
        user_text: str,
    ) -> list[dict[str, str]]:
        """Build the prompt messages using the MCP / RAG / Subagent style pipeline."""
        messages: list[dict[str, str]] = [
            await self._build_mcp_system_message(user_id=user_id, group_id=group_id)
        ]

        rag_messages = await self._build_rag_context_messages(user_id, group_id)
        if rag_messages:
            messages.extend(rag_messages)
        else:
            messages.append({"role": "user", "content": user_text})

        return messages

    async def startup_check(self) -> bool:
        """
        Run startup diagnostics to verify LLM connectivity.
        
        Returns:
            True if diagnostics pass, False otherwise.
        """
        logger.debug("[启动检查] 正在执行大模型连通性检查...")
        try:
            test_message = "你好"
            logger.debug(f"[启动检查] 发送测试消息: {test_message}")
            response = await self.llm_client.call(test_message)
            if response:
                logger.info(f"[启动成功] 大模型连通性验证通过。回复: {response[:50]}...")
                return True
            else:
                logger.error("[启动失败] 大模型返回空回复")
                return False
        except Exception as exc:
            logger.error(f"[启动失败] 大模型连通性检查失败: {type(exc).__name__}={exc}")
            logger.error("[启动诊断] 可能的问题如下:")
            logger.error("  1. 检查 .env 中的 LLM_API_KEY（当前以 ark-****... 形式隐藏）")
            logger.error(f"  2. 检查 LLM_BASE_URL: {self.llm_client.base_url}")
            logger.error("  3. 检查到火山引擎域名的网络连通性")
            logger.error("  4. 检查系统代理 / VPN 设置")
            return False

    def _extract_text_content(self, message_data: dict) -> str:
        """
        Extract plain text from OneBot V11 message payload.

        Args:
            message_data: Message object from OneBot.

        Returns:
            Extracted text content.
        """
        # 先尝试 raw_message
        if "raw_message" in message_data:
            raw_msg = message_data["raw_message"]
            if isinstance(raw_msg, str):
                return raw_msg.strip()

        # 再尝试普通字符串消息
        if "message" in message_data:
            msg = message_data["message"]
            if isinstance(msg, str):
                return msg.strip()

            # 否则按消息段数组解析
            if isinstance(msg, list):
                parts = []
                for segment in msg:
                    if isinstance(segment, dict) and segment.get("type") == "text":
                        data = segment.get("data", {})
                        text = data.get("text", "")
                        if isinstance(text, str):
                            parts.append(text)
                return "".join(parts).strip()

        return ""

    async def process_message(self, event: dict) -> None:
        """
        Process an incoming message event.

        Args:
            event: OneBot V11 message event.
        """
        # 仅处理消息事件
        if event.get("post_type") != "message":
            return

        message_type = event.get("message_type")
        if message_type not in ("private", "group"):
            logger.debug(f"忽略非私聊/群聊消息: {message_type}")
            return

        # 提取基础信息
        user_id = event.get("user_id")
        group_id = event.get("group_id") if message_type == "group" else None
        message_id = event.get("message_id")

        # 提取文本内容
        user_text = self._extract_text_content(event)

        if not user_text:
            logger.debug("收到空消息，已忽略")
            return

        logger.info(
            f"正在处理消息: type={message_type}, "
            f"user={user_id}, group={group_id}, text={user_text[:50]}"
        )

        accounting_query_reply = await self._handle_accounting_query(user_id, user_text)
        if accounting_query_reply is not None:
            await self.bot_client.send_private_msg(user_id, accounting_query_reply)
            logger.info(f"[发送成功] 已回复私聊用户 {user_id}: {accounting_query_reply[:50]}...")
            return

        recorded_accounting = await self._record_accounting_entry(user_id, user_text)

        # 将用户消息写入记忆
        if self.enable_memory:
            self.memory.add_message(
                role="user",
                content=user_text,
                user_id=user_id,
                group_id=group_id,
                metadata={"message_id": message_id},
            )

        llm_messages = await self._build_llm_messages(user_id, group_id, user_text)

        # 调用大模型
        try:
            logger.debug(f"[处理器] 正在调用大模型，user_text={user_text[:50]}...")
            response_text = await self.llm_client.call(user_text, messages=llm_messages)
            if not response_text:
                logger.warning(f"[处理器] 大模型返回空回复: {user_text[:50]}")
                response_text = "我没理解你说什么..."
        except asyncio.TimeoutError as exc:
            logger.error(f"[处理器] 大模型超时: {exc}")
            response_text = "大脑暂时掉线了，请稍后再试"
        except Exception as exc:
            logger.exception(f"[处理器] 大模型调用失败: {type(exc).__name__}={exc}")
            response_text = "大脑暂时掉线了，请稍后再试"

        if recorded_accounting is not None:
            amount, content = recorded_accounting
            amount_text = f"{amount:.2f}".rstrip("0").rstrip(".")
            response_text = f"已记录：{content} {amount_text} 元。"

        # 将助手回复写入记忆
        if self.enable_memory:
            self.memory.add_message(
                role="assistant",
                content=response_text,
                user_id=user_id,
                group_id=group_id,
            )

        # 将回复发送回 QQ
        try:
            logger.debug(f"[处理器] 正在发送回复: type={message_type}, text={response_text[:50]}...")
            if message_type == "private":
                result = await self.bot_client.send_private_msg(user_id, response_text)
                logger.info(f"[发送成功] 已回复私聊用户 {user_id}: {response_text[:50]}...")
            else:  # group
                result = await self.bot_client.send_group_msg(group_id, response_text)
                logger.info(f"[发送成功] 已回复群 {group_id}: {response_text[:50]}...")
            
            if result.get("status") != "ok":
                logger.warning(f"[发送警告] 服务端返回非成功状态: {result}")
        except Exception as exc:
            logger.exception(f"[发送失败] 类型={type(exc).__name__}, 错误={exc}")

        # 异步更新长期记忆文本，不阻塞当前回复
        self._spawn_background_task(
            self.persistent_memory.update_from_exchange(
                self.llm_client,
                user_text=user_text,
                assistant_text=response_text,
                user_id=user_id,
                group_id=group_id,
            ),
            description=f"长期记忆更新 user_id={user_id} group_id={group_id}",
        )

    def get_memory_stats(self) -> dict:
        """获取对话记忆统计信息。"""
        return self.memory.get_stats()

    def clear_user_history(self, user_id: int) -> None:
        """清除指定用户的对话历史。"""
        self.memory.clear_history(user_id=user_id)
        logger.info(f"已清除用户 {user_id} 的历史记录")

    def clear_group_history(self, group_id: int) -> None:
        """清除指定群的对话历史。"""
        self.memory.clear_history(group_id=group_id)
        logger.info(f"已清除群 {group_id} 的历史记录")
