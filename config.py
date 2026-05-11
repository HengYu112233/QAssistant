"""
Configuration management module.
Load settings from environment variables or .env file.
Avoid hardcoding sensitive information.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


class Config:
    """Application configuration manager."""

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            env_file: Path to .env file (default: .env in project root).
        """
        if env_file is None:
            env_file = str(Path(__file__).parent / ".env")
        
        if Path(env_file).exists():
            load_dotenv(env_file)

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a configuration value from environment.

        Args:
            key: Environment variable name.
            default: Default value if not found.

        Returns:
            Configuration value or default.
        """
        return os.getenv(key, default)

    @staticmethod
    def require(key: str) -> str:
        """
        Get a required configuration value.

        Args:
            key: Environment variable name.

        Returns:
            Configuration value.

        Raises:
            ValueError: If the environment variable is not set.
        """
        value = os.getenv(key)
        if value is None:
            raise ValueError(f"必需环境变量 '{key}' 未设置。"
                           f"请检查你的 .env 文件或系统环境变量。")
        return value


# Singleton instance
_config = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config


# ============================================================================
# Preset configuration accessors (for convenience)
# ============================================================================

def get_qq_ws_url() -> str:
    """QQ bot WebSocket URL (e.g., ws://127.0.0.1:3001)."""
    return get_config().require("QQ_WS_URL")


def get_llm_base_url() -> str:
    """LLM API base URL."""
    return get_config().require("LLM_BASE_URL")


def get_llm_api_key() -> str:
    """LLM API key."""
    return get_config().require("LLM_API_KEY")


def get_llm_model() -> str:
    """LLM model ID."""
    return get_config().require("LLM_MODEL")


def get_system_prompt() -> str:
    """System prompt for LLM."""
    default_prompt = "你是一个名叫'宇恒'的专属生活助理，性格幽默、回答简明扼要"
    return get_config().get("SYSTEM_PROMPT", default_prompt)


def get_log_level() -> str:
    """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
    return get_config().get("LOG_LEVEL", "INFO")
