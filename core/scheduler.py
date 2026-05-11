"""
Async reminder scheduler.

This module keeps reminder delivery separate from the main message processor so
future proactive features can grow without touching the core chat flow.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from core.bot_client import BotClient
from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ReminderScheduler:
    """Periodic reminder checker that sends proactive private messages."""

    def __init__(
        self,
        database: DatabaseManager,
        bot_client: BotClient,
        check_interval_seconds: int = 60,
    ):
        self.database = database
        self.bot_client = bot_client
        self.check_interval_seconds = check_interval_seconds
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)
        self._started = False

    async def start(self) -> None:
        """Start the scheduler and perform one immediate catch-up check."""
        await self.database.initialize()

        if not self._started:
            self.scheduler.add_job(
                self.check_due_reminders,
                trigger=IntervalTrigger(seconds=self.check_interval_seconds),
                id="check_due_reminders",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=30,
            )
            self.scheduler.start()
            self._started = True
            logger.info("提醒调度器已启动")

        await self.check_due_reminders()

    async def shutdown(self) -> None:
        """Stop the scheduler."""
        if not self._started:
            return

        self.scheduler.shutdown(wait=False)
        self._started = False
        logger.info("提醒调度器已关闭")

    async def check_due_reminders(self) -> None:
        """Check the database for due reminders and send them immediately."""
        due_reminders = await self.database.get_due_reminders(
            current_time=datetime.now(timezone.utc)
        )

        if not due_reminders:
            logger.debug("当前没有到期提醒")
            return

        for reminder in due_reminders:
            reminder_id = int(reminder["id"])
            user_id = int(reminder["user_id"])
            reminder_content = str(reminder["reminder_content"])

            message = f"⏰ 提醒：{reminder_content}"
            result = await self.bot_client.send_private_msg(user_id, message)

            if result.get("status") == "ok":
                await self.database.complete_reminder(reminder_id)
                logger.info("提醒已发送: id=%s user_id=%s", reminder_id, user_id)
            else:
                logger.warning(
                    "提醒发送失败: id=%s user_id=%s result=%s",
                    reminder_id,
                    user_id,
                    result,
                )
