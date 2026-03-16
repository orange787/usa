"""GitHub API service - wraps PyGithub for issue management."""

from __future__ import annotations

import logging
from typing import Any

from github import Github, GithubException
from github.Issue import Issue
from github.Repository import Repository

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class GitHubService:
    """Manages GitHub Issues as the requirement pool."""

    def __init__(self) -> None:
        settings = get_settings()
        self._github = Github(settings.github_token)
        self._repo: Repository = self._github.get_repo(settings.github_repo)

    @property
    def repo(self) -> Repository:
        return self._repo

    def create_issue(
        self,
        title: str,
        body: str,
        labels: list[str] | None = None,
        assignee: str | None = None,
        milestone_title: str | None = None,
    ) -> dict[str, Any]:
        """Create a new GitHub issue."""
        kwargs: dict[str, Any] = {"title": title, "body": body}

        if labels:
            kwargs["labels"] = labels
        if assignee:
            kwargs["assignee"] = assignee
        if milestone_title:
            milestone = self._find_milestone(milestone_title)
            if milestone:
                kwargs["milestone"] = milestone

        issue = self._repo.create_issue(**kwargs)
        logger.info("Created GitHub issue #%d: %s", issue.number, title)

        return {
            "number": issue.number,
            "url": issue.html_url,
            "title": issue.title,
            "state": issue.state,
        }

    def update_issue(
        self,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
        assignee: str | None = None,
    ) -> dict[str, Any]:
        """Update an existing issue."""
        issue = self._repo.get_issue(issue_number)
        kwargs: dict[str, Any] = {}

        if title is not None:
            kwargs["title"] = title
        if body is not None:
            kwargs["body"] = body
        if state is not None:
            kwargs["state"] = state
        if assignee is not None:
            kwargs["assignee"] = assignee

        if kwargs:
            issue.edit(**kwargs)

        if labels is not None:
            issue.set_labels(*labels)

        return {
            "number": issue.number,
            "url": issue.html_url,
            "title": issue.title,
            "state": issue.state,
        }

    def add_comment(self, issue_number: int, body: str) -> dict[str, Any]:
        """Add a comment to an issue."""
        issue = self._repo.get_issue(issue_number)
        comment = issue.create_comment(body)
        return {"id": comment.id, "url": comment.html_url}

    def add_labels(self, issue_number: int, labels: list[str]) -> None:
        """Add labels to an issue (without removing existing ones)."""
        issue = self._repo.get_issue(issue_number)
        for label_name in labels:
            self._ensure_label_exists(label_name)
            issue.add_to_labels(label_name)

    def remove_labels(self, issue_number: int, labels: list[str]) -> None:
        """Remove labels from an issue."""
        issue = self._repo.get_issue(issue_number)
        for label_name in labels:
            try:
                issue.remove_from_labels(label_name)
            except GithubException:
                pass

    def transition_status(self, issue_number: int, new_status: str) -> None:
        """Update the status label on an issue.

        Removes any existing status/* labels and adds the new one.
        """
        issue = self._repo.get_issue(issue_number)
        current_labels = [l.name for l in issue.labels]

        # Remove existing status labels
        status_labels = [l for l in current_labels if l.startswith("status/")]
        for sl in status_labels:
            try:
                issue.remove_from_labels(sl)
            except GithubException:
                pass

        # Add new status
        self._ensure_label_exists(new_status)
        issue.add_to_labels(new_status)
        logger.info("Issue #%d status → %s", issue_number, new_status)

    def query_issues(
        self,
        state: str = "open",
        labels: list[str] | None = None,
        sort: str = "created",
        direction: str = "desc",
    ) -> list[dict[str, Any]]:
        """Query issues with filters."""
        kwargs: dict[str, Any] = {
            "state": state,
            "sort": sort,
            "direction": direction,
        }
        if labels:
            kwargs["labels"] = labels

        issues = self._repo.get_issues(**kwargs)
        results = []
        for issue in issues:
            if issue.pull_request:
                continue
            results.append({
                "number": issue.number,
                "title": issue.title,
                "state": issue.state,
                "url": issue.html_url,
                "labels": [l.name for l in issue.labels],
                "assignee": issue.assignee.login if issue.assignee else None,
                "created_at": issue.created_at.isoformat(),
                "updated_at": issue.updated_at.isoformat(),
            })
        return results

    def get_issue(self, issue_number: int) -> dict[str, Any]:
        """Get a single issue by number."""
        issue = self._repo.get_issue(issue_number)
        return {
            "number": issue.number,
            "title": issue.title,
            "body": issue.body,
            "state": issue.state,
            "url": issue.html_url,
            "labels": [l.name for l in issue.labels],
            "assignee": issue.assignee.login if issue.assignee else None,
            "created_at": issue.created_at.isoformat(),
            "updated_at": issue.updated_at.isoformat(),
        }

    def setup_labels(self, labels_config: list[dict]) -> None:
        """Ensure all configured labels exist in the repo."""
        for label_conf in labels_config:
            self._ensure_label_exists(
                label_conf["name"],
                label_conf.get("color", "ededed"),
                label_conf.get("description", ""),
            )

    def _ensure_label_exists(
        self, name: str, color: str = "ededed", description: str = ""
    ) -> None:
        try:
            self._repo.get_label(name)
        except GithubException:
            self._repo.create_label(name=name, color=color, description=description)
            logger.info("Created label: %s", name)

    def _find_milestone(self, title: str):
        for ms in self._repo.get_milestones():
            if ms.title == title:
                return ms
        return None
