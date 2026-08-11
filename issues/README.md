# Local secondary issues

This directory stores locally published secondary issues that are decomposed from GitHub Issues in `pray4her/relationship_network`.

- Use one subdirectory per parent GitHub Issue: `issues/<parent-issue-number>/`.
- Use one Markdown file per secondary issue, numbered in dependency order with blockers first.
- Keep every secondary issue self-contained and mark an implementation-ready issue as `ready-for-agent`.
- Express blocking edges with the real parent GitHub Issue number or the numbered local secondary issue.
- Do not treat these files as permission to close or modify the parent GitHub Issue.
