"""Application configuration loaded from environment and YAML files."""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

import yaml
from pydantic_settings import BaseSettings
from pydantic import Field


BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"


class Settings(BaseSettings):
    """Environment-based settings."""

    # Telegram
    telegram_bot_token: str = ""
    telegram_group_id: int = 0

    # Lark
    lark_app_id: str = ""
    lark_app_secret: str = ""
    lark_verification_token: str = ""
    lark_encrypt_key: str = ""
    lark_group_chat_id: str = ""
    lark_webhook_url: str = ""  # 自定义机器人 Webhook（单向推送，无需公网地址）

    # GitHub
    github_token: str = ""
    github_repo: str = ""

    # LLM
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-20250514"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    llm_provider: str = Field(default="claude", alias="LLM_PROVIDER")

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/requirements.db"

    # Webhook
    webhook_host: str = ""
    webhook_port: int = 8443

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


def load_yaml(filename: str) -> dict:
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


@lru_cache()
def get_app_config() -> dict:
    return load_yaml("settings.yaml")


@lru_cache()
def get_whitelist() -> dict:
    return load_yaml("whitelist.yaml")


@lru_cache()
def get_labels_config() -> dict:
    return load_yaml("labels.yaml")


def load_prompt(name: str) -> str:
    path = CONFIG_DIR / "prompts" / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")
