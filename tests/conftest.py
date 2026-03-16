"""Shared test fixtures."""

import os
import pytest

# Set test environment variables before importing app modules
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_token")
os.environ.setdefault("GITHUB_TOKEN", "test_token")
os.environ.setdefault("GITHUB_REPO", "test/repo")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")
os.environ.setdefault("LARK_APP_ID", "test_app_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
