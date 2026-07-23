# Issue tracker: GitHub

Issues and PRDs for this repository live as GitHub Issues in the private `pray4her/relationship_network` repository.

## Tooling

- Prefer the installed GitHub connector for repository, issue, label, and comment operations.
- Use the `gh` CLI as a fallback when a required operation is unavailable through the connector.
- Infer the repository from the configured Git remote when using the CLI.

## Conventions

- Create one issue for each independently actionable unit of work.
- Keep the issue body self-contained; do not require an agent to reconstruct requirements from chat history.
- Read the full issue body, labels, and comments before acting.
- Apply or remove triage labels using the mapping in `docs/agents/triage-labels.md`.
- Close an issue only after its acceptance evidence is recorded.

## Pull requests as a triage surface

**PRs as a request surface: no.**

External pull requests do not enter the issue triage state machine. Collaborators' in-flight pull requests are handled through the normal review workflow.

## Skill terminology

- When a skill says "publish to the issue tracker", create a GitHub Issue.
- When a skill says "fetch the relevant ticket", fetch the GitHub Issue with its labels and comments.
- A `ready-for-agent` issue is fully specified and can be implemented without additional conversational context.
