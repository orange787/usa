"""Message parsing utilities."""

from __future__ import annotations

import re
from typing import Any


def extract_command(text: str) -> tuple[str, str]:
    """Extract command and arguments from a message.

    Returns:
        (command, args) tuple. command includes the slash.
    """
    match = re.match(r"^(/\w+)(?:\s+(.*))?$", text.strip(), re.DOTALL)
    if match:
        return match.group(1), (match.group(2) or "").strip()
    return "", text


def group_messages_by_thread(
    messages: list[dict],
) -> dict[str, list[dict]]:
    """Group messages by their thread_id or reply chain."""
    threads: dict[str, list[dict]] = {}

    for msg in messages:
        thread_id = msg.get("thread_id") or msg.get("reply_to_id") or msg.get("id", "default")
        threads.setdefault(thread_id, []).append(msg)

    return threads


def truncate_text(text: str, max_length: int = 4000) -> str:
    """Truncate text to a maximum length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def format_issue_list_markdown(issues: list[dict]) -> str:
    """Format a list of issues as Markdown."""
    if not issues:
        return "No issues found."

    lines = []
    for issue in issues:
        labels = issue.get("labels", [])
        priority = next((l for l in labels if l.startswith("priority/")), "")
        status = next((l for l in labels if l.startswith("status/")), "")
        state_icon = "🟢" if issue.get("state") == "open" else "✅"

        assignee = issue.get("assignee")
        assignee_text = f" | @{assignee}" if assignee else ""
        lines.append(
            f"{state_icon} **#{issue['number']}** {issue['title']}\n"
            f"   {priority} | {status}{assignee_text}"
        )

    return "\n".join(lines)


def parse_priority_from_text(text: str) -> str | None:
    """Try to extract a priority level from free text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["紧急", "urgent", "p0", "立即", "马上"]):
        return "P0"
    if any(w in text_lower for w in ["高优", "重要", "p1", "尽快"]):
        return "P1"
    if any(w in text_lower for w in ["p2", "一般"]):
        return "P2"
    if any(w in text_lower for w in ["p3", "低优", "不急", "有空"]):
        return "P3"
    return None


def sanitize_for_markdown(text: str) -> str:
    """Escape special Markdown characters to prevent formatting issues."""
    special_chars = ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]
    for char in special_chars:
        text = text.replace(char, f"\\{char}")
    return text
