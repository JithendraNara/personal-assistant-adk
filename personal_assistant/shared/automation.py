"""
Automation module — scheduled tasks and heartbeat.

Adapted from OpenClaw's src/cron/ system for scheduled agent tasks.
Provides background scheduling for daily briefings, session cleanup,
and memory persistence using APScheduler (or asyncio fallback).
"""

import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)


class AgentAutomation:
    """
    Background scheduler for automated agent tasks.

    Adapted from OpenClaw's cron/heartbeat system:
      - Scheduled briefings (like OpenClaw's cron jobs)
      - Heartbeat checks (like OpenClaw's agents.defaults.heartbeat.every)
      - Memory sync intervals
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self) -> None:
        """Start the automation scheduler."""
        self._running = True
        logger.info("Automation scheduler started")

    async def stop(self) -> None:
        """Stop all scheduled tasks."""
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
            logger.info(f"Cancelled scheduled task: {name}")
        self._tasks.clear()

    def schedule_interval(
        self,
        name: str,
        callback: Callable,
        interval_seconds: int,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        Schedule a recurring task at a fixed interval.

        Args:
            name: Task identifier.
            callback: Async function to call.
            interval_seconds: Seconds between executions.
        """
        async def _loop():
            while self._running:
                try:
                    await asyncio.sleep(interval_seconds)
                    if self._running:
                        await callback(*args, **kwargs)
                        logger.debug(f"Executed scheduled task: {name}")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error in scheduled task {name}: {e}")

        if name in self._tasks:
            self._tasks[name].cancel()
        self._tasks[name] = asyncio.create_task(_loop())
        logger.info(f"Scheduled '{name}' every {interval_seconds}s")

    def schedule_heartbeat(self, callback: Callable, interval_minutes: int = 30) -> None:
        """
        Schedule a heartbeat check (OpenClaw's heartbeat.every pattern).
        Used for session cleanup and health monitoring.
        """
        self.schedule_interval(
            name="heartbeat",
            callback=callback,
            interval_seconds=interval_minutes * 60,
        )

    def schedule_memory_sync(self, callback: Callable, interval_hours: int = 2) -> None:
        """
        Schedule periodic memory persistence.
        Saves session state to long-term memory at regular intervals.
        """
        self.schedule_interval(
            name="memory_sync",
            callback=callback,
            interval_seconds=interval_hours * 3600,
        )

    @property
    def active_tasks(self) -> list[str]:
        """List names of active scheduled tasks."""
        return [name for name, task in self._tasks.items() if not task.done()]
