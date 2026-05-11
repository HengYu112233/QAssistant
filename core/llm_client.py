"""
LLM client module for DeepSeek API integration via Volcengine Ark.
Ensures bypassing system proxy and includes retry logic.
"""

import asyncio
import logging
import socket
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI

from config import get_llm_base_url, get_llm_api_key, get_llm_model, get_system_prompt

logger = logging.getLogger(__name__)


@dataclass
class _ClientBundle:
    """封装 OpenAI 客户端及其 HTTP 传输策略。"""

    client: AsyncOpenAI
    trust_env: bool


class LLMClient:
    """
    用于通过火山引擎 Ark 调用 DeepSeek 的异步客户端。
    
    Features:
    - 直连客户端，trust_env=False，绕过系统代理
    - 回退代理客户端，trust_env=True，处理特殊网络场景
    - 指数退避重试
    - 超时保护
    - 友好的错误处理
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        request_timeout: int = 30,
        max_retries: int = 2,
    ):
        """
        Initialize LLM client.

        Args:
            base_url: LLM API base URL (default: from config).
            api_key: LLM API key (default: from config).
            model: Model ID (default: from config).
            system_prompt: System prompt for LLM (default: from config).
            request_timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
        """
        self.base_url = base_url or get_llm_base_url()
        self.api_key = api_key or get_llm_api_key()
        self.model = model or get_llm_model()
        self.system_prompt = system_prompt or get_system_prompt()
        self.request_timeout = request_timeout
        self.max_retries = max_retries

        self._direct_bundle = self._build_client_bundle(trust_env=False)
        self._proxy_bundle = self._build_client_bundle(trust_env=True)

        logger.debug(
            "LLMClient initialized: base_url=%s, model=%s, direct_trust_env=%s, proxy_fallback=%s",
            self.base_url,
            self.model,
            self._direct_bundle.trust_env,
            self._proxy_bundle.trust_env,
        )

    def _build_client_bundle(self, trust_env: bool) -> _ClientBundle:
        """按指定代理策略创建 OpenAI 客户端。"""
        http_client = httpx.AsyncClient(
            trust_env=trust_env,
            timeout=httpx.Timeout(timeout=self.request_timeout + 5),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50),
        )

        client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=http_client,
        )

        return _ClientBundle(client=client, trust_env=trust_env)

    def _is_network_switchable_error(self, exc: Exception) -> bool:
        """识别需要触发回退的 DNS 解析或连接失败。"""
        cursor: Optional[BaseException] = exc
        visited = 0

        while cursor is not None and visited < 10:
            text = str(cursor)
            if isinstance(cursor, socket.gaierror):
                return True
            if isinstance(cursor, httpx.ConnectError):
                return True
            if "getaddrinfo failed" in text:
                return True
            if "Connection error" in text:
                return True
            cursor = getattr(cursor, "__cause__", None) or getattr(cursor, "__context__", None)
            visited += 1

        return False

    async def _extract_response_text(self, response) -> str:
        """安全提取 OpenAI 响应中的文本内容。"""
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            if isinstance(content, str):
                return content.strip()
        return ""

    async def _call_once(
        self,
        bundle: _ClientBundle,
        user_message: str,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """使用指定客户端执行一次请求。"""
        logger.debug(
            "[LLM调用] 使用%s客户端，发送到 %s",
            "代理回退" if bundle.trust_env else "直连",
            self.base_url,
        )

        request_messages = messages
        if not request_messages:
            request_messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ]
        elif request_messages[0].get("role") != "system":
            request_messages = [
                {"role": "system", "content": self.system_prompt},
                *request_messages,
            ]

        response = await asyncio.wait_for(
            bundle.client.chat.completions.create(
                model=self.model,
                messages=request_messages,
            ),
            timeout=self.request_timeout,
        )

        return await self._extract_response_text(response)

    async def _call_with_retry(
        self,
        bundle: _ClientBundle,
        user_message: str,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """在同一客户端上执行指数退避重试。"""
        last_exc: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 2):
            try:
                logger.debug(
                    "[LLM尝试] 客户端=%s 第%s次/共%s次",
                    "代理回退" if bundle.trust_env else "直连",
                    attempt,
                    self.max_retries + 1,
                )
                text = await self._call_once(bundle, user_message, messages=messages)
                if text:
                    logger.info(
                        "[LLM成功] 客户端=%s 回复=%s...",
                        "代理回退" if bundle.trust_env else "直连",
                        text[:50],
                    )
                    return text

                logger.error(
                    "[LLM错误] 客户端=%s 返回空内容",
                    "代理回退" if bundle.trust_env else "直连",
                )
                return ""

            except asyncio.TimeoutError as exc:
                last_exc = exc
                logger.error(
                    "[LLM超时] 客户端=%s 第%s次/共%s次 超时=%s秒 错误=%s",
                    "代理回退" if bundle.trust_env else "直连",
                    attempt,
                    self.max_retries + 1,
                    self.request_timeout,
                    exc,
                )
            except Exception as exc:
                last_exc = exc
                logger.error(
                    "[LLM错误] 客户端=%s 第%s次/共%s次 类型=%s 错误=%s",
                    "代理回退" if bundle.trust_env else "直连",
                    attempt,
                    self.max_retries + 1,
                    type(exc).__name__,
                    exc,
                )

                # If the error is not network-related, do not waste time bouncing between clients.
                if not self._is_network_switchable_error(exc):
                    raise

            if attempt <= self.max_retries:
                wait_time = 0.8 * (2 ** (attempt - 1))
                logger.debug(
                    "[LLM重试] 客户端=%s %.1f秒后重试",
                    "代理回退" if bundle.trust_env else "直连",
                    wait_time,
                )
                await asyncio.sleep(wait_time)

        if last_exc is not None:
            raise last_exc

        raise RuntimeError("LLM call failed after all retries")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """关闭两个 HTTP 客户端。"""
        await self._direct_bundle.client.close()
        await self._proxy_bundle.client.close()
        logger.debug("LLMClient 的 HTTP 客户端已关闭")

    async def call(
        self,
        user_message: str,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """
        Call LLM with direct-first, proxy-fallback retry logic.

        Args:
            user_message: User input text.

        Returns:
            LLM response text.

        Raises:
            Exception: If all retry attempts fail.
        """
        try:
            return await self._call_with_retry(
                self._direct_bundle,
                user_message,
                messages=messages,
            )
        except Exception as direct_exc:
            if not self._is_network_switchable_error(direct_exc):
                raise

            logger.warning(
                "[LLM FALLBACK] direct client failed with %s: %s. Switching to proxy client.",
                type(direct_exc).__name__,
                direct_exc,
            )

            try:
                return await self._call_with_retry(
                    self._proxy_bundle,
                    user_message,
                    messages=messages,
                )
            except Exception as proxy_exc:
                logger.error(
                    "[LLM FALLBACK FAILED] proxy client also failed with %s: %s",
                    type(proxy_exc).__name__,
                    proxy_exc,
                )
                raise proxy_exc

    async def generate_response(
        self,
        user_message: str,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> str:
        """兼容旧接口的别名，等价于 call()。"""
        return await self.call(user_message, messages=messages)
