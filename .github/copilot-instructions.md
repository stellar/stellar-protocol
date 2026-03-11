# Copilot Instructions for stellar-protocol

This repository contains protocol specification documents, not application source code. Treat Markdown in this repository as normative technical documentation that must stay precise, internally consistent, and easy to review.

## Primary Focus: `core/`

When a task involves files under `core/`, optimize for Core Advancement Proposals (CAPs).

- Treat `core/README.md` as the source of truth for CAP statuses, process, and protocol goals.
- Treat `cap-template.md` as the default structure for new CAP drafts.
- Preserve the intent and historical context of accepted or final CAPs. Prefer surgical edits over rewriting large sections.
- Keep changes specific to the proposal being edited. Do not silently harmonize unrelated CAPs.

## CAP Authoring Rules

When creating or editing a CAP in `core/`:

- Preserve the preamble fields and their meaning: `CAP`, `Title`, `Author` or working group fields, `Status`, `Created`, `Discussion`, and `Protocol version`.
- Follow the existing section structure in the target document. Older CAPs may use a simpler structure than the current template.
- For new drafts, start from `cap-template.md` and keep the main sections in order unless there is a clear repository precedent to do otherwise.
- Keep technical statements normative and concrete. Avoid vague wording such as "improves things" or "makes it better" without specifying semantics.
- Distinguish clearly between motivation, specification, rationale, compatibility impact, security concerns, and implementation status.
- If a proposal changes protocol behavior, explain exact ledger, transaction, operation, XDR, or meta effects rather than describing only high-level intent.
- When describing protocol transitions, call out downstream impacts on validators, Horizon/RPC consumers, SDKs, and other ecosystem tooling when relevant.
- For compatibility or migration sections, be explicit about what breaks, what remains valid, and what downstream systems must update.
- For security sections, include concrete risks, invariants, abuse cases, or a short explanation of why there are no material new security concerns.
- For test cases, prefer specific scenarios and edge cases over generic placeholders.

## Style and Editing Expectations

- Keep Markdown plain, readable, and review-friendly.
- Preserve existing heading levels, capitalization style, and table formats within the edited file.
- Keep terminology consistent with Stellar protocol language already used in `core/README.md` and nearby CAPs.
- Use fenced code blocks for XDR, enum, struct, or protocol examples.
- Do not introduce unnecessary prose, marketing language, or product framing.
- Avoid changing historical status labels, dates, authorship, or protocol versions unless the task explicitly requires it.
- When referencing other proposals, use the repository's existing `CAP-xxxx` naming and relative links where appropriate.

## Scope Discipline

- If the user asks for help on a specific CAP, limit edits to that CAP and directly related supporting files.
- If the task is ambiguous, prefer reading `core/README.md`, `cap-template.md`, and the target CAP before editing.
- Do not infer implementation details that are not supported by the proposal text or task context.
- If a requested change would alter protocol semantics, surface the semantic impact clearly in the document instead of hiding it in wording changes.

## Repository Conventions

- `core/` contains CAP documents.
- `ecosystem/` contains SEP documents; do not mix SEP process guidance into CAP edits unless explicitly requested.
- `contents/` may contain supporting assets for a specific CAP; keep references aligned with the corresponding CAP number.
- Before concluding substantial Markdown edits, prefer the repository formatting command: `./bin/prettier.sh`.