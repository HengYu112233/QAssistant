"""
QQ Assistant Agent 的主入口。
负责应用生命周期：初始化、启动和优雅关闭。
"""

import asyncio
import logging
from typing import Optional

from config import get_config, get_log_level
from core.llm_client import LLMClient
from core.bot_client import BotClient
from core.database import DatabaseManager
from agent.memory import ConversationMemory
from agent.persistent_memory import PersistentMemoryStore
from agent.processor import MessageProcessor

# 配置日志
logging.basicConfig(
    level=get_log_level(),
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
)
for noisy_logger in ("httpx", "httpcore", "websockets"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class QQAssistantAgent:
    """管理整个智能体生命周期的主应用类。"""

    def __init__(self):
        """初始化智能体。"""
        self.llm_client: Optional[LLMClient] = None
        self.bot_client: Optional[BotClient] = None
        self.database: Optional[DatabaseManager] = None
        self.memory: Optional[ConversationMemory] = None
        self.persistent_memory: Optional[PersistentMemoryStore] = None
        self.processor: Optional[MessageProcessor] = None
        
        self._running = False
        self._tasks = []
        self._shutdown_started = False
        self._bot_supervisor_task: Optional[asyncio.Task] = None
        self._shutdown_event: Optional[asyncio.Event] = None

    async def startup(self) -> None:
        """初始化所有组件。"""
        logger.info("正在启动 QQ 助理智能体...")

        try:
            # 初始化配置（会校验必需环境变量）
            get_config()
            logger.debug("配置加载成功")

            # 初始化大模型客户端
            self.llm_client = LLMClient()
            logger.debug("大模型客户端初始化完成")

            # 初始化机器人客户端
            self.bot_client = BotClient()
            logger.debug("机器人客户端初始化完成")

            # 初始化数据库
            self.database = DatabaseManager()
            await self.database.initialize()
            logger.debug("数据库初始化完成")

            # 初始化记忆模块
            self.memory = ConversationMemory(max_history_size=20)
            logger.debug("记忆模块初始化完成")

            # 初始化长期记忆文本存储
            self.persistent_memory = PersistentMemoryStore()
            logger.debug("长期记忆文本存储初始化完成")

            # 初始化消息处理器
            self.processor = MessageProcessor(
                llm_client=self.llm_client,
                bot_client=self.bot_client,
                memory=self.memory,
                database=self.database,
                persistent_memory=self.persistent_memory,
                enable_memory=True,
                memory_context_window=10,
            )
            logger.debug("消息处理器初始化完成")

            # 运行启动诊断
            startup_ok = await self.processor.startup_check()
            if not startup_ok:
                logger.warning("[警告] 大模型启动检查失败，机器人将以降级模式继续运行。")

            # 注册消息处理器
            self.bot_client.add_message_handler(self.processor.process_message)

            logger.info("所有组件初始化成功")
            self._running = True

        except Exception as exc:
            logger.error(f"启动失败: {exc}")
            raise

    def _create_task_monitor(self, shutdown_event: asyncio.Event) -> None:
        """启动守护任务，保证 WebSocket 连接异常后自动恢复，而不是让主程序直接退出。"""

        self._shutdown_event = shutdown_event

        async def _supervise_bot_client() -> None:
            restart_delay_seconds = 3

            while not shutdown_event.is_set():
                bot_task = asyncio.create_task(self.bot_client.connect_and_listen())
                self._tasks.append(bot_task)

                try:
                    await bot_task
                    if shutdown_event.is_set():
                        return

                    logger.warning(
                        "机器人连接任务意外结束，%s 秒后尝试重新拉起",
                        restart_delay_seconds,
                    )
                except asyncio.CancelledError:
                    logger.debug("机器人守护任务已取消")
                    bot_task.cancel()
                    raise
                except Exception as exc:
                    logger.error(f"机器人连接任务异常退出: {type(exc).__name__}={exc}")
                finally:
                    if bot_task in self._tasks:
                        self._tasks.remove(bot_task)

                if shutdown_event.is_set():
                    return

                await asyncio.sleep(restart_delay_seconds)

        self._bot_supervisor_task = asyncio.create_task(_supervise_bot_client())
        self._tasks.append(self._bot_supervisor_task)

    async def shutdown(self) -> None:
        """优雅关闭所有组件。"""
        if self._shutdown_started:
            logger.debug("智能体正在关闭中，跳过重复关闭请求")
            return

        self._shutdown_started = True
        logger.info("正在关闭智能体...")
        
        self._running = False

        # 取消所有运行中的任务
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

        # 等待任务结束
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        # 关闭机器人客户端
        if self.bot_client:
            await self.bot_client.shutdown()

        # 关闭大模型客户端
        if self.llm_client:
            await self.llm_client.close()

        # 关闭数据库
        if self.database:
            await self.database.close()

        # 打印最终统计
        if self.processor:
            stats = self.processor.get_memory_stats()
            logger.debug(f"最终记忆统计: {stats}")

        logger.info("智能体已关闭")

async def main():
    """主入口。"""
    agent = QQAssistantAgent()
    stop_event = asyncio.Event()
    
    try:
        await agent.startup()
        agent._create_task_monitor(stop_event)
        logger.info("智能体已运行，等待停止事件...")
        await stop_event.wait()
    except asyncio.CancelledError:
        logger.info("主任务收到取消请求")
    except KeyboardInterrupt:
        logger.info("收到键盘中断，准备退出")
    except Exception as exc:
        logger.error(f"主程序发生异常: {type(exc).__name__}={exc}")
        raise
    finally:
        await agent.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已退出！")
