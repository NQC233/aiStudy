# Spec 11A Lesson Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Spec 11A backend minimum closed loop so one asset can generate, persist, and query a five-stage `lesson_plan` with evidence anchors.

**Architecture:** Introduce a new `presentations` domain entity keyed by `asset_id`, keep `assets.slides_status` as the workspace status source, and generate `lesson_plan` with deterministic rule-based logic from `parsed_json + story graph hints`. Expose two APIs (`rebuild` and `query`) and run generation asynchronously in Celery with atomic idempotency guard + row-lock write path.

**Tech Stack:** FastAPI, SQLAlchemy ORM, Alembic, Pydantic, Celery, PostgreSQL JSONB, Python unittest

---

## File Structure and Responsibilities

- Create: `backend/alembic/versions/20260401_0008_create_presentations.py`
  - Add `presentations` table and constraints for single row per asset.
- Create: `backend/app/models/presentation.py`
  - SQLAlchemy model for lesson plan snapshot + status + active run token.
- Modify: `backend/app/models/asset.py`
  - Add relationship from `Asset` to `Presentation`.
- Modify: `backend/app/models/__init__.py`
  - Export `Presentation` model.
- Create: `backend/app/schemas/slide_lesson_plan.py`
  - Pydantic contracts for lesson plan stage/anchor and API response payloads.
- Modify: `backend/app/schemas/__init__.py`
  - Export new lesson-plan schemas if project convention requires.
- Create: `backend/app/services/slide_lesson_plan_service.py`
  - Rule-based generator, validation, persistence helper, summary builder.
- Modify: `backend/app/services/__init__.py`
  - Export enqueue/query service functions.
- Modify: `backend/app/workers/tasks.py`
  - Register `enqueue_generate_asset_lesson_plan` task and state transitions.
- Modify: `backend/app/api/routes/assets.py`
  - Add rebuild/query endpoints under `/slides/lesson-plan`.
- Create: `backend/tests/test_slide_lesson_plan_service.py`
  - Unit tests for stage coverage, anchor validity, deterministic placeholder script.
- Create: `backend/tests/test_slide_lesson_plan_api.py`
  - API/service-level tests for status flow and response summary contract.
- Modify: `docs/checklist.md`
  - Update Spec 11A status and delivery record.
- Modify: `docs/specs/spec-11a-slides-domain-and-lesson-plan.md`
  - Append implementation handoff notes at file end.
- Modify: `docs/superpowers/specs/2026-04-01-spec-11a-slides-domain-and-lesson-plan-design.md`
  - Keep design/spec alignment notes if implementation deviates.

### Data/State Contract Locked In

- `presentations.version` starts at `0`, increments by `+1` only after a successful generation commit.
- `presentations.status`: `pending | processing | ready | failed`.
- `assets.slides_status` maps to `not_generated | processing | ready | failed`.
- deterministic script placeholder constant:
  - `LESSON_PLAN_PLACEHOLDER_SCRIPT = "【讲稿占位】本阶段讲解将在 Spec 11B/11C 完善。"`

### Idempotency/Concurrency Contract Locked In

- Rebuild entry only enqueues when atomic transition to `assets.slides_status=processing` succeeds.
- Worker uses `INSERT ... ON CONFLICT DO NOTHING` bootstrap for presentation row then `SELECT ... FOR UPDATE` before writes.
- Worker writes a fresh `active_run_token`; completion must match token or result is ignored as stale.

---

### Task 1: Add database model and migration

**Files:**
- Create: `backend/alembic/versions/20260401_0008_create_presentations.py`
- Create: `backend/app/models/presentation.py`
- Modify: `backend/app/models/asset.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the failing model/migration test scaffold**

```python
class PresentationModelContractTests(unittest.TestCase):
    def test_presentation_defaults_and_relationship_contract(self) -> None:
        presentation = Presentation(asset_id="asset-1")
        self.assertEqual(presentation.version, 0)
        self.assertEqual(presentation.status, "pending")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: FAIL because test file/model does not exist yet.

- [ ] **Step 3: Create migration with exact columns and constraints**

```python
op.create_table(
    "presentations",
    sa.Column("id", sa.String(length=36), primary_key=True),
    sa.Column("asset_id", sa.String(length=36), sa.ForeignKey("assets.id"), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
    sa.Column("lesson_plan", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column("error_meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
    sa.Column("active_run_token", sa.String(length=64), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
)
op.create_unique_constraint("uq_presentations_asset_id", "presentations", ["asset_id"])
op.create_index("ix_presentations_status", "presentations", ["status"])
```

- [ ] **Step 4: Add ORM model + asset relationship**

```python
presentation = relationship("Presentation", back_populates="asset", uselist=False, cascade="all, delete-orphan")
```

- [ ] **Step 5: Run compile sanity check**

Run: `python3 -m compileall backend/app backend/main.py`
Expected: PASS.

---

### Task 2: Define lesson plan schemas and response contracts

**Files:**
- Create: `backend/app/schemas/slide_lesson_plan.py`
- Modify: `backend/app/schemas/__init__.py`

- [ ] **Step 1: Write failing schema tests**

```python
class LessonPlanSchemaTests(unittest.TestCase):
    def test_lesson_plan_requires_five_stages(self) -> None:
        with self.assertRaises(ValidationError):
            AssetLessonPlanPayload(
                asset_id="asset-1",
                version=1,
                generated_at=datetime.now(timezone.utc),
                stages=[],
            )
```

- [ ] **Step 2: Run schema tests to confirm failure**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: FAIL with import/validation errors.

- [ ] **Step 3: Implement stage/anchor/payload/summary response schemas**

```python
class LessonPlanEvidenceAnchor(BaseModel):
    page_no: int
    block_ids: list[str] = Field(min_length=1)
    paragraph_ref: str | None = None
    quote: str
    selector_payload: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Add stage coverage validator (`problem..conclusion`)**

```python
required = {"problem", "method", "mechanism", "experiment", "conclusion"}
```

- [ ] **Step 5: Add anchor contract validator for reader compatibility**

```python
if anchor.page_no < 1 or not anchor.block_ids or not anchor.selector_payload:
    raise ValueError("invalid evidence anchor")
```

- [ ] **Step 6: Re-run schema test suite**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: PASS for schema-only checks.

---

### Task 3: Implement lesson-plan generator service (rule-based)

**Files:**
- Create: `backend/app/services/slide_lesson_plan_service.py`
- Modify: `backend/app/services/__init__.py`

- [ ] **Step 1: Write failing service tests for stage coverage and anchor validity**

```python
def test_generate_lesson_plan_covers_five_stages(self) -> None:
    plan = generate_lesson_plan_from_payload(payload)
    self.assertEqual([s.stage for s in plan.stages], ["problem", "method", "mechanism", "experiment", "conclusion"])
```

- [ ] **Step 2: Run service tests to verify failure**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: FAIL because service function is missing.

- [ ] **Step 3: Implement deterministic generator and placeholder script constant**

```python
LESSON_PLAN_PLACEHOLDER_SCRIPT = "【讲稿占位】本阶段讲解将在 Spec 11B/11C 完善。"
```

- [ ] **Step 4: Implement validation helper + summary builder**

```python
def build_lesson_plan_summary(plan: AssetLessonPlanPayload) -> list[LessonPlanStageSummary]:
    ...
```

- [ ] **Step 5: Re-run service tests**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: PASS.

---

### Task 4: Add enqueue/query service functions with atomic state guard

**Files:**
- Modify: `backend/app/services/slide_lesson_plan_service.py`
- Modify: `backend/app/services/__init__.py`

- [ ] **Step 1: Write failing tests for idempotent enqueue behavior**

```python
def test_enqueue_rebuild_returns_false_when_processing(self):
    asset.slides_status = "processing"
    should_enqueue = enqueue_asset_lesson_plan_rebuild(db, asset.id)[1]
    self.assertFalse(should_enqueue)

def test_enqueue_rebuild_requires_parse_ready(self):
    asset.parse_status = "processing"
    with self.assertRaises(HTTPException):
        enqueue_asset_lesson_plan_rebuild(db, asset.id)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement atomic guard and bootstrap presentation row**

```python
allowed = {"not_generated", "ready", "failed"}
updated_rows = db.execute(
    update(Asset)
    .where(Asset.id == asset_id, Asset.slides_status.in_(allowed), Asset.parse_status == "ready")
    .values(slides_status="processing")
).rowcount
```

- [ ] **Step 4: Implement query service returning status + summary**

```python
def get_asset_lesson_plan(db: Session, asset_id: str) -> AssetLessonPlanResponse:
    # response includes: asset_id, slides_status, presentation(nullable), summary
    ...
```

- [ ] **Step 5: Re-run service tests**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: PASS.

---

### Task 5: Add Celery worker task with lock/token semantics

**Files:**
- Modify: `backend/app/workers/tasks.py`
- Modify: `backend/app/services/slide_lesson_plan_service.py`

- [ ] **Step 1: Write failing worker-flow tests (or service-level transactional tests)**

```python
def test_stale_run_is_ignored(self):
    self.assertEqual(result["status"], "stale_run_ignored")

def test_duplicate_rebuild_only_enqueues_once(self):
    self.assertEqual(first_result.should_enqueue, True)
    self.assertEqual(second_result.should_enqueue, False)

def test_failure_preserves_last_successful_lesson_plan(self):
    self.assertEqual(presentation.lesson_plan, previous_success_plan)
```

- [ ] **Step 2: Run the targeted tests to see expected failure**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v`
Expected: FAIL.

- [ ] **Step 3: Register task and integrate run token checks**

```python
@celery_app.task(bind=True, name="app.workers.tasks.enqueue_generate_asset_lesson_plan")
def enqueue_generate_asset_lesson_plan(self: Task, asset_id: str) -> dict[str, str | int]:
    ...
```

- [ ] **Step 4: Implement `FOR UPDATE` write path and version increment-on-success**

```python
db.execute(text("INSERT INTO presentations (id, asset_id) VALUES (:id, :asset_id) ON CONFLICT (asset_id) DO NOTHING"), ...)
presentation = db.execute(select(Presentation).where(Presentation.asset_id == asset_id).with_for_update()).scalar_one()
presentation.version = int(presentation.version) + 1
# on failure: do not overwrite existing lesson_plan, only update status/error_meta
```

- [ ] **Step 5: Re-run tests + compile checks**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py -v && python3 -m compileall backend/app backend/main.py`
Expected: PASS.

---

### Task 6: Expose APIs in assets routes

**Files:**
- Modify: `backend/app/api/routes/assets.py`
- Modify: `backend/app/schemas/slide_lesson_plan.py`
- Modify: `backend/app/services/__init__.py`

- [ ] **Step 1: Write failing API tests for rebuild/query endpoints**

```python
def test_get_lesson_plan_returns_status_and_summary(self):
    response = client.get(f"/api/assets/{asset_id}/slides/lesson-plan")
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertIn("presentation", payload)

def test_rebuild_requires_parse_ready(self):
    response = client.post(f"/api/assets/{asset_id}/slides/lesson-plan/rebuild")
    self.assertEqual(response.status_code, 409)

def test_rebuild_is_idempotent_when_processing(self):
    response = client.post(f"/api/assets/{asset_id}/slides/lesson-plan/rebuild")
    self.assertEqual(response.status_code, 200)
    self.assertIn("已忽略重复触发", response.json()["message"])
```

- [ ] **Step 2: Run API tests and verify failure**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_api.py -v`
Expected: FAIL with 404 or missing route.

- [ ] **Step 3: Add `POST /slides/lesson-plan/rebuild` route**

```python
if should_enqueue:
    enqueue_generate_asset_lesson_plan.delay(asset.id)
```

- [ ] **Step 4: Add `GET /slides/lesson-plan` route with summary payload**

```python
return get_asset_lesson_plan(db, asset_id)
```

- [ ] **Step 5: Re-run API tests**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_api.py -v`
Expected: PASS.

---

### Task 7: End-to-end verification and regression checks

**Files:**
- Test: `backend/tests/test_slide_lesson_plan_service.py`
- Test: `backend/tests/test_slide_lesson_plan_api.py`
- Test: `backend/tests/test_mindmap_story_graph.py`
- Test: `backend/tests/test_task_reliability_service.py`

- [ ] **Step 1: Run new lesson-plan test suites**

Run: `python3 -m unittest backend/tests/test_slide_lesson_plan_service.py backend/tests/test_slide_lesson_plan_api.py -v`
Expected: PASS.

- [ ] **Step 2: Run existing key regression suites**

Run: `python3 -m unittest backend/tests/test_mindmap_story_graph.py backend/tests/test_task_reliability_service.py -v`
Expected: PASS.

- [ ] **Step 3: Run backend compile sanity check**

Run: `python3 -m compileall backend/app backend/main.py`
Expected: PASS.

- [ ] **Step 4: Capture verification notes for checklist entry**

Record exact commands and pass/fail outcomes for docs update.

---

### Task 8: Update delivery documents

**Files:**
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-11a-slides-domain-and-lesson-plan.md`
- Modify: `docs/superpowers/specs/2026-04-01-spec-11a-slides-domain-and-lesson-plan-design.md`

- [ ] **Step 1: Mark Spec 11A as completed in checklist board**

```md
- [x] Spec 11A：演示文稿领域模型与备课层生成
```

- [ ] **Step 2: Add Spec 11A delivery record section in checklist**

Include completed scope, changed files, verification commands, known gaps, next-step recommendation.

- [ ] **Step 3: Append handoff notes to Spec 11A file tail**

Include actual completion, deviations, unresolved items, next handoff recommendation.

- [ ] **Step 4: If implementation deviates, sync design spec notes**

Update the design doc with concise delta notes to keep plan/spec/implementation aligned.

- [ ] **Step 5: Final docs consistency check**

Run: `python3 -m compileall backend/app backend/main.py`
Expected: PASS; docs updated with no contradiction against implementation.

---

## Commit Strategy (Frequent, Small)

- Commit 1: `feat: add presentations domain model and migration for lesson plan`
- Commit 2: `feat: add lesson plan schemas and generation service`
- Commit 3: `feat: add lesson plan rebuild/query api and worker task`
- Commit 4: `test: add lesson plan service and api coverage`
- Commit 5: `docs: update spec 11a checklist and handoff notes`

## Out of Scope Guardrails

- Do not generate `slides_dsl` in this plan.
- Do not add Reveal rendering or frontend playback entry in this plan.
- Do not integrate LLM for `script` generation in this plan.
- Do not expand to Spec 11B/11C fields except minimal compatibility-safe placeholders.
