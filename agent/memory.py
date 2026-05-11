"""
Memory management module for agent context and conversation history.
Supports in-memory storage with future extensibility to databases.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in conversation history."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)


class ConversationMemory:
    """
    In-memory conversation history storage.
    
    Supports:
    - Per-user/group conversation tracking
    - Context window management
    - Future: Database backend integration
    """

    def __init__(self, max_history_size: int = 20):
        """
        Initialize conversation memory.

        Args:
            max_history_size: Max messages to keep per conversation.
        """
        self.max_history_size = max_history_size
        # Key: f"user_{user_id}" or f"group_{group_id}"
        self._conversations: Dict[str, List[Message]] = {}

    def _get_key(self, user_id: Optional[int] = None, group_id: Optional[int] = None) -> str:
        """Generate storage key for a conversation."""
        if user_id:
            return f"user_{user_id}"
        elif group_id:
            return f"group_{group_id}"
        else:
            raise ValueError("Either user_id or group_id must be provided")

    def add_message(
        self,
        role: str,
        content: str,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Add a message to conversation history.

        Args:
            role: "user" or "assistant".
            content: Message content.
            user_id: User ID (for private messages).
            group_id: Group ID (for group messages).
            metadata: Optional metadata (message_id, etc).
        """
        key = self._get_key(user_id, group_id)
        if key not in self._conversations:
            self._conversations[key] = []

        message = Message(role=role, content=content, metadata=metadata or {})
        self._conversations[key].append(message)

        # Trim history if exceeds max size
        if len(self._conversations[key]) > self.max_history_size:
            removed = self._conversations[key].pop(0)
            logger.debug(f"Trimmed old message from {key}: {removed.content[:50]}...")

    def get_history(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """
        Get conversation history.

        Args:
            user_id: User ID (for private messages).
            group_id: Group ID (for group messages).
            limit: Max number of messages to return.

        Returns:
            List of messages.
        """
        key = self._get_key(user_id, group_id)
        history = self._conversations.get(key, [])
        
        if limit:
            history = history[-limit:]
        
        return history

    def clear_history(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
    ) -> None:
        """
        Clear conversation history.

        Args:
            user_id: User ID (for private messages).
            group_id: Group ID (for group messages).
        """
        key = self._get_key(user_id, group_id)
        if key in self._conversations:
            self._conversations[key].clear()
            logger.info(f"Cleared history for {key}")

    def get_context_for_llm(
        self,
        user_id: Optional[int] = None,
        group_id: Optional[int] = None,
        context_window: int = 10,
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM API.

        Args:
            user_id: User ID.
            group_id: Group ID.
            context_window: Number of recent messages to include.

        Returns:
            List of {"role": "...", "content": "..."} dicts.
        """
        history = self.get_history(user_id, group_id, limit=context_window)
        return [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]

    def get_stats(self) -> Dict:
        """Get memory statistics."""
        total_conversations = len(self._conversations)
        total_messages = sum(len(msgs) for msgs in self._conversations.values())
        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "conversations": {
                k: len(msgs) for k, msgs in self._conversations.items()
            }
        }
