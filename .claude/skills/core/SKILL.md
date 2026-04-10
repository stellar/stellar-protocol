---
name: core
description: 'Work on Stellar Core Advancement Proposals in core/. Use when editing CAP documents, checking CAP status fields, or syncing a CAP preamble Status with the corresponding entry in core/README.md.'
argument-hint: 'CAP number or core/ task, for example: sync CAP-0082 status with core/README.md'
---

# Core CAP Workflow

Use this skill for tasks in `core/`, especially when creating, editing, reviewing, or validating Core Advancement Proposals (CAPs).

## When to Use

- Edit a CAP under `core/cap-xxxx.md`.
- Create a new CAP draft from `cap-template.md`.
- Verify that a CAP's `Status` field matches the corresponding entry in `core/README.md`.
- Update a CAP's status and keep the index tables in `core/README.md` synchronized.

## Sources of Truth

- Use `core/README.md` for the allowed CAP statuses and how CAPs are grouped in the proposal tables.
- Use `cap-template.md` for the default structure of new CAP drafts.
- Use the target CAP document for the exact preamble fields, terminology, and section structure already in use.

## Status Synchronization Rules

When a task involves a CAP status:

1. Read the CAP preamble in `core/cap-xxxx.md` and find the `Status` line.
2. Read the matching CAP row in `core/README.md`.
3. Compare the status text exactly, including values such as `Draft`, `Accepted`, `Implemented`, `Final`, `Rejected`, `Awaiting Decision`, `FCP: Acceptance`, `FCP: Rejection`, or `Superseded: ...`.
4. If the status is intended to change, update both places in the same edit.
5. If the new status changes which README table the CAP belongs in, move the row to the correct section instead of only changing the text in place.
6. Keep the CAP title, number, and author fields aligned with the corresponding README row when you touch the status entry.
7. If there is a mismatch but the intended new status is not clear from the task or surrounding context, stop and ask rather than guessing which side is correct.

## CAP Editing Rules

- Preserve preamble fields and their meaning: `CAP`, `Title`, `Author` or working group fields, `Status`, `Created`, `Discussion`, and `Protocol version`.
- Follow the existing section structure of the target CAP. Older CAPs may not match the current template exactly.
- Keep protocol language normative and concrete. Describe exact ledger, transaction, operation, XDR, or meta effects.
- Make downstream effects explicit when relevant, especially for validators, Horizon/RPC consumers, and SDKs.
- Keep compatibility, migration, and security sections specific and actionable.
- Prefer surgical edits over broad rewrites.

## Procedure

1. Read `core/README.md`, `cap-template.md` if relevant, and the target `core/cap-xxxx.md`.
2. Determine whether the task is a drafting task, a status-sync task, or both.
3. For status-sync tasks, update the CAP preamble and `core/README.md` together.
4. For status transitions, confirm the CAP row is located in the correct README section.
5. Preserve existing Markdown style, heading levels, and table formatting.
6. Before finishing substantial Markdown edits, run `./bin/prettier.sh` when appropriate.

## Do Not

- Do not change unrelated CAPs while fixing one CAP's status.
- Do not silently infer a new status from partial evidence.
- Do not mix SEP process guidance into `core/` tasks unless explicitly requested.
- Do not rewrite accepted or final CAPs beyond the requested change.