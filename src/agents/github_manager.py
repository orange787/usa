"""Agent 3: GitHub Manager Agent - Requirement pool CRUD via GitHub Issues."""

from __future__ import annotations

import logging
from typing import Any

from src.core.config import get_app_config, get_labels_config
from src.core.models import RequirementStatus
from src.services.github_service import GitHubService

logger = logging.getLogger(__name__)

# Map requirement type/priority to GitHub labels
TYPE_LABEL_MAP = {
    "feature": "type/feature",
    "bug": "type/bug",
    "data": "type/data",
    "event": "type/event",
    "optimization": "type/optimization",
}

PRIORITY_LABEL_MAP = {
    "P0": "priority/P0",
    "P1": "priority/P1",
    "P2": "priority/P2",
    "P3": "priority/P3",
}

STATUS_LABEL_MAP = {
    "todo": "status/todo",
    "in-progress": "status/in-progress",
    "review": "status/review",
    "done": "status/done",
}


class GitHubManagerAgent:
    """Manages the GitHub Issues requirement pool."""

    def __init__(self, github_service: GitHubService) -> None:
        self.gh = github_service
        self.config = get_app_config()

    # ── Skill: issue_create ───────────────────────────────────────────────

    async def create_issue(self, requirement_data: dict) -> dict[str, Any]:
        """Create a GitHub Issue from a structured requirement."""
        title = requirement_data.get("title", "Untitled")
        req_type = requirement_data.get("type", "feature")
        priority = requirement_data.get("priority", "P2")

        # Build issue body
        body = self._build_issue_body(requirement_data)

        # Collect labels
        labels = [
            TYPE_LABEL_MAP.get(req_type, "type/feature"),
            PRIORITY_LABEL_MAP.get(priority, "priority/P2"),
            "status/todo",
            "source/ops",
        ]

        result = self.gh.create_issue(
            title=title,
            body=body,
            labels=labels,
        )

        logger.info("Created issue #%s: %s", result["number"], title)
        return result

    # ── Skill: issue_update ───────────────────────────────────────────────

    async def update_issue(
        self, issue_number: int, updates: dict
    ) -> dict[str, Any]:
        """Update an existing issue."""
        return self.gh.update_issue(issue_number, **updates)

    # ── Skill: issue_query ────────────────────────────────────────────────

    async def query_issues(
        self,
        state: str = "all",
        labels: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Query issues with optional filters."""
        return self.gh.query_issues(state=state, labels=labels)

    # ── Skill: status_transition ──────────────────────────────────────────

    async def update_status(self, issue_number: int, new_status: str) -> None:
        """Transition an issue's status label."""
        self.gh.transition_status(issue_number, new_status)

    # ── Skill: add_comment ────────────────────────────────────────────────

    async def add_comment(self, issue_number: int, body: str) -> dict[str, Any]:
        """Add a comment to an issue."""
        return self.gh.add_comment(issue_number, body)

    # ── Skill: label_manage ───────────────────────────────────────────────

    async def setup_labels(self) -> None:
        """Initialize all labels from config."""
        labels_config = get_labels_config()
        label_list = labels_config.get("labels", [])
        self.gh.setup_labels(label_list)
        logger.info("Setup %d labels", len(label_list))

    # ── Skill: report_generate ────────────────────────────────────────────

    async def generate_report(self) -> dict[str, Any]:
        """Generate a requirements statistics report."""
        all_issues = self.gh.query_issues(state="all")

        stats = {
            "total": len(all_issues),
            "open": 0,
            "closed": 0,
            "by_status": {},
            "by_type": {},
            "by_priority": {},
        }

        for issue in all_issues:
            if issue["state"] == "open":
                stats["open"] += 1
            else:
                stats["closed"] += 1

            for label in issue.get("labels", []):
                if label.startswith("status/"):
                    status = label.replace("status/", "")
                    stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                elif label.startswith("type/"):
                    typ = label.replace("type/", "")
                    stats["by_type"][typ] = stats["by_type"].get(typ, 0) + 1
                elif label.startswith("priority/"):
                    pri = label.replace("priority/", "")
                    stats["by_priority"][pri] = stats["by_priority"].get(pri, 0) + 1

        return stats

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _build_issue_body(req: dict) -> str:
        """Build Markdown body for a GitHub issue."""
        desc = req.get("description", "")
        background = req.get("background", "")
        criteria = req.get("acceptance_criteria", [])
        areas = req.get("affected_areas", [])
        notes = req.get("requester_notes", "")
        requester = req.get("requester_name", "运营团队")

        criteria_md = "\n".join(f"- [ ] {c}" for c in criteria) if criteria else "- [ ] TBD"
        areas_md = ", ".join(areas) if areas else "TBD"

        return (
            f"## 背景\n{background or 'N/A'}\n\n"
            f"## 需求描述\n{desc}\n\n"
            f"## 验收标准\n{criteria_md}\n\n"
            f"## 影响范围\n{areas_md}\n\n"
            f"## 备注\n{notes or 'N/A'}\n\n"
            f"---\n"
            f"📌 来源: {requester} (via Telegram)\n"
            f"🤖 由 Ops-Dev Bridge Bot 自动创建"
        )
