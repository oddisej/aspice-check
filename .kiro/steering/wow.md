---
inclusion: always
---
<!------------------------------------------------------------------------------------
   Add rules to this file or a short description and have Kiro refine them for you.
   
   Learn about inclusion modes: https://kiro.dev/docs/steering/#inclusion-modes
------------------------------------------------------------------------------------->

## Git Commit After Task Completion

After completing each top-level task from a spec's `tasks.md`, create a git commit with:
- Stage all changed/new files relevant to the task
- Commit message format: `feat(spec-name): Task N — short task title`
- Example: `feat(dora-compliance-test-environment): Task 1 — Set up project structure and core data models`
- Do NOT commit `.venv/`, `__pycache__/`, or other generated/ignored files

## Default Branch

The default branch is `master`, not `main`. Use `master` in all CI rules, git commands, and branch references.

## Commit Spec Files

When the last task is completed commit spec files with:
- Stage all files in the `.kiro/specs/{spec-name}/` directory
- Commit message format: `docs(spec-name): Add/Update requirements|design|tasks`
- Example: `docs(comment-priority): Add requirements, design, and tasks`
