"""
Channel registry — discover, manage, and route to channel adapters.

Adapted from OpenClaw's src/channels/registry.ts pattern.
Maintains a registry of active channels and handles message routing.
"""

import logging
from typing import Optional

from personal_assistant.channels.base import BaseChannel

logger = logging.getLogger(__name__)


class ChannelRegistry:
    """
    Registry for managing channel adapters.

    OpenClaw equivalent: src/channels/registry.ts
    Supports per-channel routing and lifecycle management.
    """

    def __init__(self):
        self._channels: dict[str, BaseChannel] = {}

    def register(self, channel: BaseChannel) -> None:
        """Register a channel adapter."""
        self._channels[channel.name] = channel
        logger.info(f"Registered channel: {channel.name}")

    def unregister(self, name: str) -> None:
        """Remove a channel adapter from the registry."""
        if name in self._channels:
            del self._channels[name]
            logger.info(f"Unregistered channel: {name}")

    def get(self, name: str) -> Optional[BaseChannel]:
        """Get a channel by name."""
        return self._channels.get(name)

    def list_channels(self) -> list[str]:
        """List all registered channel names."""
        return list(self._channels.keys())

    async def start_all(self) -> None:
        """Start all registered channel listeners."""
        for name, channel in self._channels.items():
            try:
                await channel.start()
                logger.info(f"Started channel: {name}")
            except Exception as e:
                logger.error(f"Failed to start channel {name}: {e}")

    async def stop_all(self) -> None:
        """Stop all registered channel listeners."""
        for name, channel in self._channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped channel: {name}")
            except Exception as e:
                logger.error(f"Failed to stop channel {name}: {e}")
