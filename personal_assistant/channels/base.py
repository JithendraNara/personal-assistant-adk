"""
Base channel abstract class — contract for all channel adapters.

Adapted from OpenClaw's channel architecture (src/channels/).
Each channel adapter must implement receive(), send(), and session key generation.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


logger = logging.getLogger(__name__)


@dataclass
class InboundMessage:
    """A message received from a channel."""
    text: str
    sender_id: str
    channel_name: str
    metadata: dict = field(default_factory=dict)
    # OpenClaw concepts
    peer_id: Optional[str] = None    # DM peer identifier
    group_id: Optional[str] = None   # Group/guild identifier
    account_id: str = "default"      # Channel account (OpenClaw multi-account)


@dataclass
class OutboundMessage:
    """A message to send back through a channel."""
    text: str
    recipient_id: str
    metadata: dict = field(default_factory=dict)


class BaseChannel(ABC):
    """
    Abstract base channel — implements the adapter pattern for messaging platforms.

    OpenClaw equivalent: src/channels/registry.ts + individual channel adapters.
    Each channel provides:
      - receive: Transform platform message → InboundMessage
      - send: Transform ADK response → platform-specific message
      - session_key: Generate per-sender session isolation key
    """

    def __init__(self, name: str, config: dict | None = None):
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(f"channel.{name}")

    @abstractmethod
    async def receive(self, raw_data: Any) -> InboundMessage:
        """Transform raw platform data into a standardized InboundMessage."""
        ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> bool:
        """Send a response back to the platform. Returns True on success."""
        ...

    def session_key(self, sender_id: str) -> str:
        """
        Generate a session key for per-sender isolation.
        OpenClaw pattern: agent:<agentId>:<mainKey>
        """
        return f"channel:{self.name}:{sender_id}"

    @abstractmethod
    async def start(self) -> None:
        """Start the channel listener (webhook server, bot polling, etc)."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Gracefully stop the channel listener."""
        ...
