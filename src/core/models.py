"""Data models for the Ops-Dev Requirement Bridge System."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────

class RequirementType(str, enum.Enum):
    FEATURE = "feature"
    BUG = "bug"
    DATA = "data"
    EVENT = "event"
    OPTIMIZATION = "optimization"


class Priority(str, enum.Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class RequirementStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    REVIEW = "review"
    DONE = "done"
    REJECTED = "rejected"


class ApprovalAction(str, enum.Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


class MessageSource(str, enum.Enum):
    TELEGRAM = "telegram"
    LARK = "lark"
    GITHUB = "github"


# ── Message Models ────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single message from any platform."""

    id: str
    source: MessageSource
    chat_id: str
    user_id: str
    user_name: str
    text: str = ""
    media_urls: list[str] = Field(default_factory=list)
    reply_to_id: Optional[str] = None
    thread_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageThread(BaseModel):
    """A group of related messages forming a discussion thread."""

    thread_id: str
    messages: list[ChatMessage] = Field(default_factory=list)
    source: MessageSource = MessageSource.TELEGRAM
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Requirement Models ────────────────────────────────────────────────────

class Requirement(BaseModel):
    """Structured requirement extracted from conversations."""

    id: Optional[str] = None
    title: str
    description: str
    type: RequirementType = RequirementType.FEATURE
    priority: Priority = Priority.P2
    status: RequirementStatus = RequirementStatus.DRAFT
    acceptance_criteria: list[str] = Field(default_factory=list)
    background: str = ""
    affected_areas: list[str] = Field(default_factory=list)
    requester_notes: str = ""

    # Tracking
    source_messages: list[str] = Field(default_factory=list)
    github_issue_number: Optional[int] = None
    github_issue_url: Optional[str] = None
    tg_message_id: Optional[str] = None
    lark_message_id: Optional[str] = None

    # Metadata
    requester_id: str = ""
    requester_name: str = ""
    assignee: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ApprovalRequest(BaseModel):
    """An approval request sent to an admin."""

    id: str
    requirement: Requirement
    approver_id: str
    approver_platform: MessageSource
    action: Optional[ApprovalAction] = None
    comment: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class QuestionList(BaseModel):
    """Questions from dev team that need ops confirmation."""

    id: str
    requirement_id: str
    github_issue_number: int
    questions: list[str]
    context: str = ""
    approved_by_lark_admin: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Report Models ─────────────────────────────────────────────────────────

class DailyDigest(BaseModel):
    """Daily status digest."""

    date: datetime
    new_count: int = 0
    in_progress_count: int = 0
    done_count: int = 0
    overdue_count: int = 0
    pending_confirmation_count: int = 0
    changes: list[str] = Field(default_factory=list)
    overdue_items: list[str] = Field(default_factory=list)
    pending_items: list[str] = Field(default_factory=list)


# ── Event Models ──────────────────────────────────────────────────────────

class EventType(str, enum.Enum):
    # TG events
    TG_MESSAGE_RECEIVED = "tg.message.received"
    TG_COMMAND_RECEIVED = "tg.command.received"
    TG_KEYWORD_DETECTED = "tg.keyword.detected"
    TG_APPROVAL_RESPONSE = "tg.approval.response"

    # Requirement events
    REQ_EXTRACTED = "requirement.extracted"
    REQ_APPROVED = "requirement.approved"
    REQ_REJECTED = "requirement.rejected"
    REQ_MODIFIED = "requirement.modified"

    # GitHub events
    GH_ISSUE_CREATED = "github.issue.created"
    GH_ISSUE_UPDATED = "github.issue.updated"
    GH_STATUS_CHANGED = "github.status.changed"

    # Lark events
    LARK_MESSAGE_RECEIVED = "lark.message.received"
    LARK_CARD_ACTION = "lark.card.action"
    LARK_APPROVAL_RESPONSE = "lark.approval.response"

    # Sync events
    SYNC_PROGRESS_UPDATE = "sync.progress.update"
    SYNC_DAILY_DIGEST = "sync.daily.digest"
    SYNC_ESCALATION = "sync.escalation"

    # System events
    SYSTEM_ERROR = "system.error"


class Event(BaseModel):
    """Event passed through the event bus."""

    type: EventType
    data: dict = Field(default_factory=dict)
    source: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
