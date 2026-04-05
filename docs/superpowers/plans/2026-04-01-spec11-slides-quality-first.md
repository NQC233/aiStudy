# Spec 11 (A/B/C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a quality-first slide generation pipeline with lesson-plan -> DSL -> Reveal playback, excluding TTS/auto-advance.

**Architecture:** Implement Spec 11 in three sequential slices: 11A (domain + lesson plan), 11B (DSL + quality gates), 11C (Reveal rendering + workspace entry). Each slice ships runnable behavior with API contracts and tests before moving to the next slice.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, PostgreSQL(JSONB), Vue 3 + TypeScript + Vite, Reveal.js

---

### Task 1: Spec 11A Domain Model + Migration

**Files:**
- Create: `backend/app/models/slide_deck.py`
- Create: `backend/alembic/versions/<timestamp>_create_slide_decks.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_slide_deck_model.py`

- [ ] **Step 1: Write the failing test**

```python
def test_slide_deck_defaults():
    # status/version/lesson_plan defaults
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm backend python -m unittest tests/test_slide_deck_model.py -v`
Expected: FAIL with missing model/table.

- [ ] **Step 3: Write minimal implementation**

```python
class SlideDeck(Base):
    __tablename__ = "slide_decks"
    ...
```

- [ ] **Step 4: Run test + migration checks**

Run: `docker compose run --rm backend python -m unittest tests/test_slide_deck_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/slide_deck.py backend/alembic/versions/... backend/app/models/__init__.py backend/tests/test_slide_deck_model.py
git commit -m "feat: add slide deck domain model and migration"
```

### Task 2: Spec 11A Lesson Plan Generator

**Files:**
- Create: `backend/app/schemas/slides.py`
- Create: `backend/app/services/slide_lesson_plan_service.py`
- Modify: `backend/app/services/__init__.py`
- Test: `backend/tests/test_slide_lesson_plan_service.py`

- [ ] **Step 1: Write failing tests for storyline coverage**

```python
def test_lesson_plan_covers_five_stages():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose run --rm backend python -m unittest tests/test_slide_lesson_plan_service.py -v`
Expected: FAIL because service/schema missing.

- [ ] **Step 3: Implement minimal lesson-plan generation**

```python
def build_lesson_plan(parsed_payload, story_nodes):
    return {...}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `docker compose run --rm backend python -m unittest tests/test_slide_lesson_plan_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/slides.py backend/app/services/slide_lesson_plan_service.py backend/app/services/__init__.py backend/tests/test_slide_lesson_plan_service.py
git commit -m "feat: add lesson plan generation service for slide decks"
```

### Task 3: Spec 11A API + Worker Integration

**Files:**
- Modify: `backend/app/api/routes/assets.py`
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/schemas/__init__.py`
- Test: `backend/tests/test_slide_deck_api.py`

- [ ] **Step 1: Write failing API tests**
- [ ] **Step 2: Run tests to confirm failure**
Run: `docker compose run --rm backend python -m unittest tests/test_slide_deck_api.py -v`
- [ ] **Step 3: Add endpoints and worker task hooks**
- [ ] **Step 4: Run tests to confirm pass**
- [ ] **Step 5: Commit**

### Task 4: Spec 11B DSL Schema + Generator

**Files:**
- Create: `backend/app/services/slide_dsl_service.py`
- Modify: `backend/app/schemas/slides.py`
- Test: `backend/tests/test_slide_dsl_service.py`

- [ ] **Step 1: Write failing test for DSL shape**
- [ ] **Step 2: Run and verify fail**
Run: `docker compose run --rm backend python -m unittest tests/test_slide_dsl_service.py -v`
- [ ] **Step 3: Implement minimal DSL generator with 6-8 templates**
- [ ] **Step 4: Run tests and verify pass**
- [ ] **Step 5: Commit**

### Task 5: Spec 11B Quality Gates + Local Fix Loop

**Files:**
- Create: `backend/app/services/slide_quality_service.py`
- Create: `backend/app/services/slide_fix_service.py`
- Test: `backend/tests/test_slide_quality_service.py`

- [ ] **Step 1: Write failing tests for must-pass and quality-score**
- [ ] **Step 2: Run and verify fail**
Run: `docker compose run --rm backend python -m unittest tests/test_slide_quality_service.py -v`
- [ ] **Step 3: Implement validators and page-level fix orchestration**
- [ ] **Step 4: Run tests and verify pass**
- [ ] **Step 5: Commit**

### Task 6: Spec 11C Reveal Render Payload + Frontend Player

**Files:**
- Create: `backend/app/services/slide_render_service.py`
- Create: `frontend/src/pages/slides/SlidesPlayerPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/api/assets.ts`
- Test: `backend/tests/test_slide_render_service.py`

- [ ] **Step 1: Write failing render-payload tests**
- [ ] **Step 2: Run and verify fail**
Run: `docker compose run --rm backend python -m unittest tests/test_slide_render_service.py -v`
- [ ] **Step 3: Implement render payload builder and frontend player page**
- [ ] **Step 4: Run backend tests + frontend build**
Run: `docker compose run --rm backend python -m unittest tests/test_slide_render_service.py -v && npm run build --prefix frontend`
Expected: PASS + build success
- [ ] **Step 5: Commit**

### Task 7: Workspace Entry + Citation Backlink

**Files:**
- Modify: `frontend/src/pages/workspace/WorkspacePage.vue`
- Modify: `frontend/src/pages/slides/SlidesPlayerPage.vue`
- Modify: `frontend/src/styles/base.css`

- [ ] **Step 1: Add workspace entry UI and status badge**
- [ ] **Step 2: Add citation click -> reader jump contract**
- [ ] **Step 3: Verify with frontend build**
Run: `npm run build --prefix frontend`
- [ ] **Step 4: Commit**

### Task 8: Verification + Docs Handoff

**Files:**
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-11a-slides-domain-and-lesson-plan.md`
- Modify: `docs/specs/spec-11b-slides-dsl-and-quality-gates.md`
- Modify: `docs/specs/spec-11c-reveal-render-and-workspace-entry.md`

- [ ] **Step 1: Run full verification commands**

Run:
- `python3 -m compileall backend/app backend/main.py`
- `docker compose run --rm backend python -m unittest tests/test_slide_*.py -v`
- `npm run build --prefix frontend`

Expected: all pass.

- [ ] **Step 2: Update checklist and sub-spec handoff records**
- [ ] **Step 3: Commit**
