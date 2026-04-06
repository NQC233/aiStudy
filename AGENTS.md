# AGENTS Governance Rules

This file is the highest-priority project convention for agent behavior in this repository.

## 1) Priority and source of truth

When instructions conflict, use this order:

1. User's direct instruction in current conversation
2. `AGENTS.md` (this file)
3. Project specs under `docs/specs/*.md`
4. Process docs (`docs/agent-spec-playbook.md`, `docs/checklist.md`)
5. Any external skill/system templates (including Superpowers defaults)

## 2) Spec location policy (anti-drift)

- Authoritative specs MUST live in `docs/specs/`.
- `docs/superpowers/` is NON-authoritative working memory/reference area.
- Do NOT treat files in `docs/superpowers/` as execution source unless user explicitly says so.
- Do NOT create new authoritative spec/plan files under `docs/superpowers/`.

## 3) Execution entry protocol

Before coding, every agent MUST:

1. Read `docs/checklist.md`
2. Identify current target spec in `docs/specs/`
3. Read the target spec file(s)
4. Implement only in-scope work

## 4) Completion protocol

After each implementation round, every agent MUST:

1. Update `docs/checklist.md` with factual status
2. Append handoff notes to the tail of the corresponding file in `docs/specs/`
3. Record unresolved issues and next-step recommendation

## 5) Scope control rules

- One round = one bounded objective.
- Do not silently switch to a different spec.
- Do not introduce parallel process conventions without user approval.
- If a new constraint appears, write it into `docs/checklist.md` as a decision or blocker.

## 6) Current project-specific guardrail

For this repository, default execution context is the mainline docs system:

- `docs/requirements.md`
- `docs/architecture.md`
- `docs/checklist.md`
- `docs/specs/*.md`

Anything outside this set is supportive only unless the user explicitly promotes it.
