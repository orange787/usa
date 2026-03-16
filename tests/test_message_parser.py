"""Tests for message parser utilities."""

from src.utils.message_parser import (
    extract_command,
    group_messages_by_thread,
    truncate_text,
    parse_priority_from_text,
)


def test_extract_command():
    assert extract_command("/submit") == ("/submit", "")
    assert extract_command("/submit some args") == ("/submit", "some args")
    assert extract_command("not a command") == ("", "not a command")


def test_group_messages_by_thread():
    messages = [
        {"id": "1", "thread_id": "t1", "text": "a"},
        {"id": "2", "thread_id": "t1", "text": "b"},
        {"id": "3", "thread_id": "t2", "text": "c"},
    ]
    groups = group_messages_by_thread(messages)
    assert len(groups["t1"]) == 2
    assert len(groups["t2"]) == 1


def test_truncate_text():
    assert truncate_text("short", 100) == "short"
    assert len(truncate_text("a" * 5000, 4000)) == 4000
    assert truncate_text("a" * 5000, 4000).endswith("...")


def test_parse_priority():
    assert parse_priority_from_text("这个很紧急") == "P0"
    assert parse_priority_from_text("高优先级") == "P1"
    assert parse_priority_from_text("P2 一般需求") == "P2"
    assert parse_priority_from_text("不急，有空再做") == "P3"
    assert parse_priority_from_text("普通文本") is None
