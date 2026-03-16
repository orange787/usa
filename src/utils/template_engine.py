"""Template rendering utilities using Jinja2."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.core.config import CONFIG_DIR

_env: Environment | None = None


def get_template_env() -> Environment:
    """Get or create the Jinja2 template environment."""
    global _env
    if _env is None:
        template_dir = CONFIG_DIR / "prompts"
        _env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(default=False),
        )
    return _env


def render_template(template_name: str, **kwargs) -> str:
    """Render a template with the given context variables."""
    env = get_template_env()
    template = env.get_template(template_name)
    return template.render(**kwargs)


def render_daily_report(
    date: str,
    new_count: int,
    in_progress_count: int,
    done_count: int,
    pending_count: int,
    changes: list[str],
    overdue_items: list[str],
    pending_items: list[str],
) -> str:
    """Render the daily report template."""
    changes_text = "\n".join(f"- {c}" for c in changes) if changes else "- 无变更"
    overdue_text = "\n".join(f"- {o}" for o in overdue_items) if overdue_items else "- 无"
    pending_text = "\n".join(f"- {p}" for p in pending_items) if pending_items else "- 无"

    return (
        f"📊 需求日报 - {date}\n\n"
        f"## 总览\n"
        f"- 新增需求: {new_count}\n"
        f"- 进行中: {in_progress_count}\n"
        f"- 已完成: {done_count}\n"
        f"- 待确认: {pending_count}\n\n"
        f"## 今日变更\n{changes_text}\n\n"
        f"## ⚠️ 需关注\n{overdue_text}\n\n"
        f"## 待运营确认\n{pending_text}"
    )
