"""
Channel adapters package — multi-channel messaging support.

Adapted from OpenClaw's src/channels/ architecture:
  - BaseChannel with send/receive contracts
  - Channel registry for discovering and managing channels
  - Per-channel session isolation

Supported channels:
  - Webhook: Generic incoming HTTP webhook
  - Telegram: Telegram Bot API (requires BOT_TOKEN)
  - Discord: Discord Bot API (requires BOT_TOKEN)
"""

from personal_assistant.channels.base import BaseChannel
from personal_assistant.channels.registry import ChannelRegistry

__all__ = ["BaseChannel", "ChannelRegistry"]
