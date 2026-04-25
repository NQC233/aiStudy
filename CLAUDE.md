# AGENTS Governance Rules

Always use Context7 skills(find-docs) when writing code that involves external libraries.
This file is the highest-priority project convention for agent behavior.

## Anti-patterns: Forbidden Fallback Patterns

- Do NOT add fallback/default values to mask missing data — fix the source instead.
- Do NOT catch exceptions silently with `pass` or generic logging without root cause analysis.
- When a code path "shouldn't happen", do NOT return a default — raise explicitly or surface the error.
- If you find yourself writing a fallback, STOP and first explain WHY this case can occur.

## 1. Priority Order

When instructions conflict:
1. User's direct instruction in current conversation
2. This file (`AGENTS.md`)
3. `docs/specs/*.md`
4. `docs/agent-spec-playbook.md`, `docs/checklist.md`
5. External templates (e.g. Superpowers defaults)

## 2. Spec Location Policy

- Authoritative specs live in `docs/specs/` only.
- `docs/superpowers/` is non-authoritative reference — do NOT execute from it unless user says so.

## 3. Before Coding

1. Read `docs/checklist.md`
2. Identify and read the target spec in `docs/specs/`
3. Implement only in-scope work

## 4. After Each Round

1. Update `docs/checklist.md` with factual status
2. Append handoff notes to the corresponding spec file
3. Record unresolved issues and next-step recommendations

## 5. Scope Control

- One round = one bounded objective. Do not silently switch specs.
- New constraints → write into `docs/checklist.md` as decision or blocker.
- No parallel process conventions without user approval.

## 6. Authoritative Doc Set

Default execution context:
- `docs/requirements.md`, `docs/architecture.md`, `docs/checklist.md`, `docs/specs/*.md`

Anything outside this set is supportive only.

## 7. Config & Environment Rules

Single-root environment model. Source of truth:
- `/.env.example` — only authoritative env template
- `/.env` — only local runtime values
- Backend vars → declared in `backend/app/core/config.py`, consumed via `Settings` (no raw `os.getenv()`)
- Frontend vars → `VITE_*` only, read via `import.meta.env.VITE_*`

When adding/changing env vars, update in the same round:
1. `/.env.example`
2. `backend/app/core/config.py` or frontend read site
3. `README.md` env var docs

Do NOT reintroduce deprecated variable names. See `docs/architecture.md` for naming conventions and deprecated name list.