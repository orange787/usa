# Daily Report Generation Prompt

Generate a concise daily status report for the ops-dev requirement bridge.

## Input
- List of requirements with their current statuses
- Changes since last report
- Overdue items

## Output Format (Markdown)

```
📊 需求日报 - {date}

## 总览
- 新增需求: {count}
- 进行中: {count}
- 已完成: {count}
- 待确认: {count}

## 今日变更
{list of status changes}

## ⚠️ 需关注
{overdue or blocked items}

## 待运营确认
{items needing ops confirmation}
```

## Guidelines
- Keep it brief and scannable
- Highlight blockers and overdue items prominently
- Use emoji sparingly for visual scanning
- Include links to GitHub issues where relevant
