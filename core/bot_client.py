"""
QQ bot client module for WebSocket communication via NapCat/OneBot V11.
Handles connection management, message receiving, and automatic reconnection.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets
from websockets.exceptions import WebSocketException

from config import get_qq_ws_url

logger = logging.getLogger(__name__)


MessageHandler = Callable[[dict], None]


class BotClient:
    """
    QQ 机器人（OneBot V11 协议）的异步 WebSocket 客户端。
    
    Features:
    - 连接丢失后自动重连
    - 优雅关闭
    - 消息路由到处理器
    - 心跳/ping 支持
    """

    def __init__(
        self,
        ws_url: Optional[str] = None,
        reconnect_delay: int = 3,
        reconnect_max_attempts: Optional[int] = None,
        ping_interval: int = 20,
        ping_timeout: int = 20,
    ):
        """
        Initialize bot client.

        Args:
            ws_url: WebSocket URL (default: from config).
            reconnect_delay: Delay between reconnection attempts (seconds).
            reconnect_max_attempts: Max reconnection attempts (None = infinite).
            ping_interval: Ping interval for keepalive (seconds).
            ping_timeout: Ping timeout (seconds).
        """
        self.ws_url = ws_url or get_qq_ws_url()
        self.reconnect_delay = reconnect_delay
        self.reconnect_max_attempts = reconnect_max_attempts
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout

        self._ws = None
        self._message_handlers = []
        self._running = False
        self._reconnect_count = 0

        logger.debug(f"BotClient 已初始化: ws_url={self.ws_url}")

    def add_message_handler(self, handler: MessageHandler) -> None:
        """
        Register a message handler callback.

        Args:
            handler: Async or sync function(message: dict) -> None
        """
        self._message_handlers.append(handler)
        logger.debug(f"已注册消息处理器: {handler.__name__}")

    async def send_private_msg(self, user_id: int, message: str) -> dict:
        """
        Send a private message to a user.

        Args:
            user_id: Target user ID.
            message: Message content.

        Returns:
            API response.
        """
        return await self._send_action(
            action="send_private_msg",
            params={"user_id": user_id, "message": message},
        )

    async def send_group_msg(self, group_id: int, message: str) -> dict:
        """
        Send a message to a group.

        Args:
            group_id: Target group ID.
            message: Message content.

        Returns:
            API response.
        """
        return await self._send_action(
            action="send_group_msg",
            params={"group_id": group_id, "message": message},
        )

    async def _send_action(self, action: str, params: dict) -> dict:
        """
        Send an API action to the bot.

        Args:
            action: Action name (e.g., "send_private_msg").
            params: Action parameters.

        Returns:
            Response dictionary.
        """
        if self._ws is None:
            logger.error(f"[发送失败] WebSocket 连接为空，无法发送动作: {action}")
            return {"status": "failed", "retcode": -1, "error": "WebSocket 未连接"}

        import uuid
        payload = {
            "action": action,
            "params": params,
            "echo": f"{action}-{uuid.uuid4()}",
        }

        try:
            await self._ws.send(json.dumps(payload, ensure_ascii=False))
            logger.info(f"[发送成功] {action} 目标={params.get('user_id', params.get('group_id'))}")
            return {"status": "ok", "retcode": 0}
        except Exception as exc:
            logger.error(f"[发送失败] action={action}, params={params}, 错误类型={type(exc).__name__}, 错误={exc}")
            return {"status": "failed", "retcode": -1, "error": str(exc)}

    async def _handle_message(self, raw_data: str) -> None:
        """
        Process incoming message and dispatch to handlers.

        Args:
            raw_data: Raw JSON string from WebSocket.
        """
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            logger.warning(f"收到非 JSON 消息: {raw_data}")
            return

        logger.debug(f"[接收] {json.dumps(data, ensure_ascii=False, indent=2)}")

        # Dispatch to all registered handlers
        for handler in self._message_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as exc:
                logger.error(f"消息处理器 {handler.__name__} 出错: {exc}")

    async def connect_and_listen(self) -> None:
        """
        Connect to WebSocket and listen for messages with auto-reconnect.
        Run this as a long-lived task.
        """
        self._running = True
        while self._running:
            try:
                logger.info(f"正在连接 {self.ws_url}...")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=self.ping_interval,
                    ping_timeout=self.ping_timeout,
                    close_timeout=10,
                    max_size=2**24,
                ) as ws:
                    self._ws = ws
                    self._reconnect_count = 0
                    logger.info("已连接到机器人 WebSocket")

                    async for message in ws:
                        if isinstance(message, bytes):
                            try:
                                message = message.decode("utf-8")
                            except UnicodeDecodeError:
                                logger.warning("收到非 UTF-8 二进制消息")
                                continue
                        await self._handle_message(message)

            except WebSocketException as exc:
                logger.error(f"WebSocket 连接错误: {exc}")
                self._ws = None
            except asyncio.CancelledError:
                logger.debug("WebSocket 连接已取消")
                self._running = False
                break
            except Exception as exc:
                logger.error(f"WebSocket 循环中发生未预期错误: {exc}")
                self._ws = None

            # Reconnection logic
            if not self._running:
                break

            self._reconnect_count += 1
            if (
                self.reconnect_max_attempts is not None
                and self._reconnect_count > self.reconnect_max_attempts
            ):
                logger.error("已达到最大重连次数，停止重试")
                self._running = False
                break

            logger.info(
                f"将在 {self.reconnect_delay} 秒后重连 "
                f"(第 {self._reconnect_count} 次)"
            )
            await asyncio.sleep(self.reconnect_delay)

    async def shutdown(self) -> None:
        """Gracefully shutdown the bot client."""
        logger.debug("正在关闭机器人客户端...")
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception as exc:
                logger.error(f"关闭 WebSocket 时出错: {exc}")
            logger.debug("机器人客户端已关闭")
