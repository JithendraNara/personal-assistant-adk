"""
Webhook channel adapter — generic incoming HTTP webhook handler.

Adapted from OpenClaw's src/channels/web/ pattern.
Receives messages via HTTP POST and sends responses back.
"""

import logging
from typing import Any

from personal_assistant.channels.base import BaseChannel, InboundMessage, OutboundMessage

logger = logging.getLogger(__name__)


class WebhookChannel(BaseChannel):
    """
    Generic webhook channel — receives messages via HTTP POST.
    Suitable for custom integrations and testing.
    """

    def __init__(self, config: dict | None = None):
        super().__init__(name="webhook", config=config)
        self._response_queue: dict[str, str] = {}

    async def receive(self, raw_data: Any) -> InboundMessage:
        """Transform webhook payload into InboundMessage."""
        if isinstance(raw_data, dict):
            return InboundMessage(
                text=raw_data.get("message", raw_data.get("text", "")),
                sender_id=raw_data.get("sender_id", raw_data.get("user_id", "webhook_user")),
                channel_name=self.name,
                metadata=raw_data.get("metadata", {}),
            )
        return InboundMessage(
            text=str(raw_data),
            sender_id="webhook_user",
            channel_name=self.name,
        )

    async def send(self, message: OutboundMessage) -> bool:
        """Queue response for webhook caller to retrieve."""
        self._response_queue[message.recipient_id] = message.text
        logger.debug(f"Queued response for {message.recipient_id}")
        return True

    def get_response(self, recipient_id: str) -> str | None:
        """Retrieve queued response for a recipient."""
        return self._response_queue.pop(recipient_id, None)

    async def start(self) -> None:
        """Webhook doesn't need a persistent listener."""
        logger.info("Webhook channel ready (handles HTTP POST)")

    async def stop(self) -> None:
        """No-op for webhook."""
        pass
