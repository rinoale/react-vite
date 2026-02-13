# 3-Agent Workflow

## Quick Start

1. Create a task file from `tasks/TASK_TEMPLATE.md`:
   - `tasks/TASK-001-<topic>.md`
2. Add the task to `AI_SYNC.md` under `Backlog`.
3. Assign owner agent and reviewers.
4. Move task to `In Progress` when execution starts.
5. Owner fills handoff section in task file.
6. Reviewer runs `tasks/HANDOFF_TEMPLATE.md` and records findings.
7. Owner resolves findings, then move task to `Done`.
8. Log key decision in `AI_SYNC.md` -> `Decisions`.

## Minimum Policy

- No direct `Done` without one peer review.
- No architecture change without a `Decisions` entry.
- If blocked for more than 1 cycle, add one clear unblock request in `Blocked`.

## Suggested Cadence

- Every 30-60 minutes:
  - each agent updates its lane in `AI_SYNC.md`
  - stale tasks are either moved to `Blocked` or re-assigned

