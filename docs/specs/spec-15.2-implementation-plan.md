# Spec 15.2 Remaining Work Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining Spec 15.2 work by wiring config-backed HTML validation into the real generation path, exposing page-scoped rebuild controls in the playback UI, and proving the flow with backend tests, frontend E2E, and targeted manual verification.

**Architecture:** Keep the existing runtime gate and playback snapshot consumers authoritative. The missing work is the producer side: enrich rendered pages with page-level validation metadata immediately after HTML generation and before runtime bundle assembly, so the same data naturally flows into persisted page artifacts, runtime bundle summaries, failed-only rebuild targeting, and playback gate decisions. Then expose the existing rebuild API semantics in `SlidesPlayPage.vue` without introducing a second status system or a new API schema.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Pydantic, Python unittest/pytest, Vue 3, TypeScript, Vite, Playwright.

---

## Scope Of This Plan

This plan covers only the still-open Spec 15.2 items described in the current handoff and spec tail:

- wire `SLIDES_HTML_CANVAS_*` and `SLIDES_HTML_VALIDATION_*` into the HTML generation and validation seam
- make runtime gate and failed-only rebuild consume real page validation results rather than summary-only metadata
- add playback-page UI for page-scoped HTML rebuild and failed-only rebuild
- add backend coverage and frontend Playwright coverage for the remaining paths
- run targeted verification and update the authoritative docs

This plan does **not** reopen already-completed Spec 15.2 work such as pseudo-ready gate fixes, fullscreen support, or the existing rebuild API contract.

## File Structure

**Backend producer and gate wiring**
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Modify: `backend/app/services/slide_html_authoring_service.py`
- Modify: `backend/app/services/slide_runtime_bundle_service.py`
- Modify: `backend/app/services/slide_dsl_service.py`
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/app/core/config.py`

**Frontend playback rebuild UI**
- Modify: `frontend/src/pages/slides/SlidesPlayPage.vue`
- Modify: `frontend/src/api/assets.ts`
- Modify if needed: `frontend/src/components/slides/SlidesDeckRuntime.vue`
- Modify if needed: `frontend/src/components/slides/HtmlSlideFrame.vue`

**Tests**
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Modify: `backend/tests/test_slide_html_authoring_service.py`
- Modify if needed: `backend/tests/test_llm_service.py`
- Modify: existing slides playback Playwright spec under `frontend/tests/` or `frontend/playwright/` based on current repo location

**Docs and status**
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md`

## Shared Invariants

Every task below must preserve these invariants:

- `slides_status`, `presentation.status`, and `playback_status` continue to derive from one authoritative runtime view
- page-level validation metadata lives on rendered pages and flows forward into runtime summaries; do not create a parallel store
- page-scoped rebuild keeps using the existing payload contract:
  - single page HTML rebuild: `{ from_stage: 'html', page_numbers: [n] }`
  - failed-only rebuild: `{ from_stage: 'html', failed_only: true }`
- validation metadata uses the current field names:
  - `render_meta.validation.status`
  - `render_meta.validation.blocking`
  - `render_meta.validation.reason`
  - `render_meta.runtime_gate_status`

### Task 1: Wire Page Validation Into The Generation Seam

**Files:**
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Test: `backend/tests/test_slide_generation_v2_service.py`

- [ ] **Step 1: Write the failing backend test for validation enrichment after HTML generation**

Add a test that exercises the seam immediately after `render_slide_pages(...)` and before runtime bundle assembly. The test should assert that when HTML validation is enabled, each rendered page receives config-backed validation metadata and that the downstream runtime bundle builder sees those fields.

```python
def test_build_runtime_bundle_uses_page_validation_from_rendered_pages() -> None:
    rendered_pages = [
        {
            "page_number": 1,
            "html": "<html><body><div class='slide-root'>OK</div></body></html>",
            "render_meta": {},
        },
        {
            "page_number": 2,
            "html": "<html><body><div class='slide-root broken'>BAD</div></body></html>",
            "render_meta": {},
        },
    ]

    bundle = finalize_rendered_slide_pages_for_runtime(
        rendered_pages,
        canvas_width=1600,
        canvas_height=900,
        validation_enabled=True,
        validate_page_html=lambda **kwargs: {
            1: {"status": "passed", "blocking": False, "reason": None},
            2: {"status": "failed", "blocking": True, "reason": "overflow_detected"},
        }[kwargs["page_number"]],
        runtime_bundle_builder=build_runtime_bundle,
    )

    assert rendered_pages[0]["render_meta"]["validation"]["status"] == "passed"
    assert rendered_pages[1]["render_meta"]["validation"]["status"] == "failed"
    assert bundle["playable_page_count"] == 1
    assert bundle["failed_page_numbers"] == [2]
```

- [ ] **Step 2: Run the failing test and verify the failure is about missing enrichment behavior**

Run: `pytest backend/tests/test_slide_generation_v2_service.py -k validation -q`
Expected: FAIL because the current generation path does not yet enrich `rendered_pages[*].render_meta.validation` before bundle assembly.

- [ ] **Step 3: Implement the minimal enrichment helper in `slide_generation_v2_service.py`**

Add a focused helper that receives the rendered pages, applies the canvas config, runs page validation, writes validation metadata to each page, and only then hands the list to `runtime_bundle_builder(...)`.

```python
def finalize_rendered_slide_pages_for_runtime(
    rendered_pages: list[dict[str, Any]],
    *,
    canvas_width: int,
    canvas_height: int,
    validation_enabled: bool,
    validate_page_html: Callable[..., dict[str, Any]],
    runtime_bundle_builder: Callable[[list[dict[str, Any]]], dict[str, Any]],
) -> dict[str, Any]:
    for page in rendered_pages:
        render_meta = page.setdefault("render_meta", {})
        render_meta.setdefault(
            "canvas",
            {
                "width": canvas_width,
                "height": canvas_height,
            },
        )

        if validation_enabled:
            validation = validate_page_html(
                page_number=int(page.get("page_number") or 0),
                html=str(page.get("html") or ""),
                canvas_width=canvas_width,
                canvas_height=canvas_height,
            )
        else:
            validation = {
                "status": "skipped",
                "blocking": False,
                "reason": "validation_disabled",
            }

        render_meta["validation"] = validation
        render_meta["runtime_gate_status"] = "failed" if validation.get("blocking") else "ready"

    return runtime_bundle_builder(rendered_pages)
```

- [ ] **Step 4: Replace the inline seam in the real generation flow with the helper**

Update the main flow around:

```python
rendered_subset, html_meta = render_slide_pages(...)
...
runtime_bundle = runtime_bundle_builder(rendered_slide_pages)
```

so that it becomes conceptually:

```python
rendered_subset, html_meta = render_slide_pages(...)
rendered_subset = [_to_json_safe(page) for page in rendered_subset]
error_meta["html_generation"] = [_to_json_safe(item) for item in html_meta]
...
runtime_bundle = finalize_rendered_slide_pages_for_runtime(
    rendered_slide_pages,
    canvas_width=settings.slides_html_canvas_width,
    canvas_height=settings.slides_html_canvas_height,
    validation_enabled=settings.slides_html_validation_enabled,
    validate_page_html=validate_rendered_slide_page,
    runtime_bundle_builder=lambda pages: _to_json_safe(runtime_bundle_builder(pages)),
)
```

- [ ] **Step 5: Run the targeted backend test again**

Run: `pytest backend/tests/test_slide_generation_v2_service.py -k validation -q`
Expected: PASS.

### Task 2: Make HTML Validation Consume Real Canvas Config And Produce Stable Metadata

**Files:**
- Modify: `backend/tests/test_slide_html_authoring_service.py`
- Modify: `backend/app/services/slide_html_authoring_service.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_slide_html_authoring_service.py`

- [ ] **Step 1: Write the failing tests for config-backed canvas validation**

Add tests that prove the validator reads the real settings and returns stable metadata for the three required outcomes: passed, failed, and skipped/timeout-safe fallback.

```python
def test_validate_rendered_slide_page_reports_failure_for_overflow() -> None:
    result = validate_rendered_slide_page(
        page_number=3,
        html="<html><body><div style='height:2000px'>overflow</div></body></html>",
        canvas_width=1600,
        canvas_height=900,
        timeout_sec=8,
    )

    assert result["status"] == "failed"
    assert result["blocking"] is True
    assert result["reason"] == "overflow_detected"


def test_validate_rendered_slide_page_reports_skipped_when_disabled() -> None:
    result = build_slide_validation_result(
        enabled=False,
        page_number=1,
        html="<html></html>",
        canvas_width=1600,
        canvas_height=900,
        timeout_sec=8,
    )

    assert result == {
        "status": "skipped",
        "blocking": False,
        "reason": "validation_disabled",
    }
```

- [ ] **Step 2: Run the failing authoring-service tests**

Run: `pytest backend/tests/test_slide_html_authoring_service.py -k validation -q`
Expected: FAIL because the current validator does not yet expose the stable config-backed behavior under test.

- [ ] **Step 3: Implement a minimal validator API that normalizes result shape**

In `slide_html_authoring_service.py`, expose a single entry point that always returns the same metadata shape and accepts the canvas config explicitly.

```python
def build_slide_validation_result(
    *,
    enabled: bool,
    page_number: int,
    html: str,
    canvas_width: int,
    canvas_height: int,
    timeout_sec: int,
) -> dict[str, Any]:
    if not enabled:
        return {
            "status": "skipped",
            "blocking": False,
            "reason": "validation_disabled",
        }

    return validate_rendered_slide_page(
        page_number=page_number,
        html=html,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        timeout_sec=timeout_sec,
    )
```

Keep the first implementation minimal. The validator does not need full browser measurement in this round, but it must be config-backed, observable, and able to block obvious contract violations.

- [ ] **Step 4: Verify the settings surface is complete and consistently named**

Ensure `backend/app/core/config.py` includes the authoritative fields already referenced by the spec and handoff:

```python
slides_html_canvas_width: int = 1600
slides_html_canvas_height: int = 900
slides_html_validation_enabled: bool = True
slides_html_validation_timeout_sec: int = 8
```

Do not introduce duplicate aliases or a second naming scheme.

- [ ] **Step 5: Run the authoring-service validation tests again**

Run: `pytest backend/tests/test_slide_html_authoring_service.py -k validation -q`
Expected: PASS.

### Task 3: Align Runtime Gate With Real Page Validation Results

**Files:**
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Modify: `backend/app/services/slide_runtime_bundle_service.py`
- Modify: `backend/app/services/slide_dsl_service.py`
- Test: `backend/tests/test_slide_generation_v2_service.py`

- [ ] **Step 1: Write the failing test for failed-page derivation from page metadata**

Add a test that feeds rendered pages with mixed validation outcomes into the runtime bundle service and verifies that failed pages are derived from page-level metadata rather than from a precomputed summary blob.

```python
def test_runtime_bundle_derives_failed_pages_from_page_validation_metadata() -> None:
    pages = [
        {
            "page_number": 1,
            "render_meta": {
                "validation": {"status": "passed", "blocking": False, "reason": None},
                "runtime_gate_status": "ready",
            },
        },
        {
            "page_number": 2,
            "render_meta": {
                "validation": {"status": "failed", "blocking": True, "reason": "overflow_detected"},
                "runtime_gate_status": "failed",
            },
        },
    ]

    bundle = build_runtime_bundle(pages)

    assert bundle["playable_page_count"] == 1
    assert bundle["failed_page_numbers"] == [2]
    assert bundle["playback_status"] == "partial_ready"
```

- [ ] **Step 2: Run the failing gate test**

Run: `pytest backend/tests/test_slide_generation_v2_service.py -k failed_page_numbers -q`
Expected: FAIL because the current implementation still privileges summary-only metadata somewhere in the path.

- [ ] **Step 3: Make the runtime bundle builder prefer page-level validation fields**

In `slide_runtime_bundle_service.py`, update the logic so that each page contributes to `playable_page_count`, `failed_page_numbers`, and overall `playback_status` from `render_meta.validation` and `render_meta.runtime_gate_status` first.

Conceptually:

```python
validation = page.get("render_meta", {}).get("validation") or {}
gate_status = page.get("render_meta", {}).get("runtime_gate_status")

is_failed = bool(validation.get("blocking")) or gate_status == "failed"
is_ready = not is_failed
```

Do not delete existing summary fields if other callers still read them. Instead, make summary fields derivative, not authoritative.

- [ ] **Step 4: Ensure DSL/playback snapshot code keeps the same source of truth**

In `slide_dsl_service.py`, verify that any snapshot assembly or playback summary logic reads the runtime bundle fields that now originate from page-level validation, rather than reconstructing an alternate interpretation.

- [ ] **Step 5: Run the targeted gate tests again**

Run: `pytest backend/tests/test_slide_generation_v2_service.py -k "failed_page_numbers or playback_status" -q`
Expected: PASS.

### Task 4: Keep The HTML Prompt Contract Consistent With The Runtime Canvas Contract

**Files:**
- Modify: `backend/tests/test_llm_service.py`
- Modify: `backend/app/services/llm_service.py`
- Test: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the failing test for fixed-canvas prompt instructions**

Add a test that asserts the HTML authoring prompt includes the configured canvas width/height, fixed single-page requirements, and no-scroll constraint.

```python
def test_build_slide_html_prompt_includes_fixed_canvas_contract() -> None:
    prompt = build_slide_html_prompt(
        scene_spec={"page_number": 2, "title": "Method"},
        canvas_width=1600,
        canvas_height=900,
    )

    assert "1600x900" in prompt
    assert "single presentation page" in prompt
    assert "do not create internal scrolling" in prompt
```

- [ ] **Step 2: Run the failing LLM-service test**

Run: `pytest backend/tests/test_llm_service.py -k canvas -q`
Expected: FAIL because the prompt contract is not yet strict or explicit enough.

- [ ] **Step 3: Tighten the prompt contract in the smallest possible way**

Update the HTML authoring prompt builder so it explicitly instructs the model to produce a fixed-size slide page using the configured dimensions, safe area, and no-scroll requirement.

```python
canvas_clause = (
    f"Render exactly one presentation page on a fixed {canvas_width}x{canvas_height} canvas. "
    "The root container must fit the canvas without vertical expansion or internal scrolling. "
    "Do not generate a long document or a responsive article layout."
)
```

Do not redesign the whole prompt strategy in this task.

- [ ] **Step 4: Run the prompt-contract test again**

Run: `pytest backend/tests/test_llm_service.py -k canvas -q`
Expected: PASS.

### Task 5: Expose Page-Scoped HTML Rebuild Controls In The Playback UI

**Files:**
- Modify: `frontend/src/pages/slides/SlidesPlayPage.vue`
- Modify: `frontend/src/api/assets.ts`
- Modify if needed: `frontend/src/components/slides/SlidesDeckRuntime.vue`
- Test: existing playback-related frontend tests plus Playwright in Task 7

- [ ] **Step 1: Add a failing UI test or component assertion for per-page rebuild controls**

If the repo already has a component test setup for slides pages, add a test that expects the playback page to render:

- a page selector or page-target control
- a button that triggers `{ from_stage: 'html', page_numbers: [n] }`
- a button that triggers `{ from_stage: 'html', failed_only: true }`

If there is no practical component-test harness here, skip directly to Playwright in Task 7 and document that the first failing automated proof for this UI will be E2E.

- [ ] **Step 2: Implement the smallest playback-page control surface**

In `SlidesPlayPage.vue`, add local UI state for the selected page number and wire it to the existing rebuild API call.

The control surface must support:

```ts
await rebuildSlidesRuntimeBundle(assetId, {
  from_stage: 'html',
  page_numbers: [selectedPageNumber],
})

await rebuildSlidesRuntimeBundle(assetId, {
  from_stage: 'html',
  failed_only: true,
})
```

Use the current playback snapshot to determine:

- the available page range
- whether failed pages exist
- whether the failed-only action should be disabled

- [ ] **Step 3: Add loading, disabled, and refresh behavior**

After each rebuild action:

- set an in-flight state to block duplicate submissions
- refresh the slides snapshot on success
- surface a concise error message on failure
- clear stale success/error messages on the next action

Keep the logic inside `SlidesPlayPage.vue` unless the file is already too large to reason about.

- [ ] **Step 4: Verify the UI does not create a parallel rebuild model**

The playback page must continue to use backend-provided snapshot data such as:

- `runtime_bundle.page_count`
- `playable_page_count`
- `failed_page_numbers`
- `rebuild_meta`

Do not cache an independent failed-page list in the frontend.

### Task 6: Add Backend Coverage For Failed-Only Rebuild Targeting

**Files:**
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Test: `backend/tests/test_slide_generation_v2_service.py`

- [ ] **Step 1: Write the failing tests for rebuild targeting semantics**

Add tests that prove:

- `page_numbers=[3]` rebuilds only page 3 from `html`
- `failed_only=True` rebuilds only pages listed in `failed_page_numbers`
- `failed_only=True` with no failed pages becomes a no-op or returns the current bundle without rebuilding unrelated pages

```python
def test_rebuild_runtime_bundle_targets_only_requested_html_pages() -> None:
    result = rebuild_runtime_bundle(
        asset_id="asset-1",
        from_stage="html",
        page_numbers=[3],
        failed_only=False,
        ...
    )

    assert result.rebuilt_page_numbers == [3]


def test_rebuild_runtime_bundle_targets_only_failed_pages_when_failed_only_enabled() -> None:
    result = rebuild_runtime_bundle(
        asset_id="asset-1",
        from_stage="html",
        page_numbers=None,
        failed_only=True,
        ...
    )

    assert result.rebuilt_page_numbers == [2, 5]
```

- [ ] **Step 2: Run the failing rebuild-targeting tests**

Run: `pytest backend/tests/test_slide_generation_v2_service.py -k rebuild -q`
Expected: FAIL if the current targeting still depends on stale summaries or lacks explicit no-failed-pages behavior.

- [ ] **Step 3: Implement the minimal targeting fix using real failed page metadata**

Update the rebuild-selection logic in `slide_generation_v2_service.py` so that:

- explicit `page_numbers` take priority when present
- otherwise `failed_only=True` derives its target set from the current runtime bundle's `failed_page_numbers`
- the target set is de-duplicated and sorted

Conceptually:

```python
if page_numbers:
    target_page_numbers = sorted({int(page) for page in page_numbers})
elif failed_only:
    target_page_numbers = sorted({int(page) for page in runtime_bundle.get("failed_page_numbers", [])})
else:
    target_page_numbers = []
```

- [ ] **Step 4: Run the rebuild-targeting tests again**

Run: `pytest backend/tests/test_slide_generation_v2_service.py -k rebuild -q`
Expected: PASS.

### Task 7: Add Playwright Coverage For Playback Rebuild Controls

**Files:**
- Modify: the existing slides playback Playwright spec in the repo
- Test: that same Playwright spec file

- [ ] **Step 1: Write the failing E2E scenario for page-scoped rebuild**

Extend the current playback E2E to cover:

- opening the playback page for an asset with runtime pages
- selecting a page number for HTML rebuild
- submitting the rebuild action
- verifying the correct network payload contains:

```json
{ "from_stage": "html", "page_numbers": [2] }
```

- [ ] **Step 2: Write the failing E2E scenario for failed-only rebuild**

Add another scenario that verifies:

- failed page numbers are surfaced in the playback UI
- the failed-only action is enabled only when failed pages exist
- the outgoing payload contains:

```json
{ "from_stage": "html", "failed_only": true }
```

- [ ] **Step 3: Run the Playwright spec and confirm the failures are on missing UI behavior**

Run the repo's existing Playwright command for the target spec file.
Expected: FAIL because the playback page does not yet expose the requested controls or payloads.

- [ ] **Step 4: Finish the UI wiring and rerun the same Playwright spec**

Run the same Playwright command.
Expected: PASS.

### Task 8: Run Focused Verification Before Updating Docs

**Files:**
- No code changes required in this task

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
pytest backend/tests/test_slide_generation_v2_service.py -q
pytest backend/tests/test_slide_html_authoring_service.py -q
pytest backend/tests/test_llm_service.py -q
```

Expected: PASS.

- [ ] **Step 2: Run the frontend/Playwright target for playback rebuild controls**

Run the repo's standard Playwright command for the modified playback spec.
Expected: PASS.

- [ ] **Step 3: Do one browser-based manual verification pass if local services are available**

Manual checklist:

- open the playback page for a runtime bundle with at least one failed page
- trigger a single-page HTML rebuild
- trigger a failed-only rebuild
- confirm the playback snapshot refreshes and page counts/failed-page counts change as expected
- confirm no empty playable state is shown after a successful rebuild

If the local stack cannot be started in this round, record the blocker explicitly in `docs/checklist.md` and the spec handoff note.

### Task 9: Update The Authoritative Status Docs

**Files:**
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md`

- [ ] **Step 1: Update `docs/checklist.md` with factual completion status**

Record:

- the backend validation producer wiring is complete or partially complete
- playback page per-page rebuild UI status
- exact verification commands run and whether they passed
- any remaining gaps, especially if browser-measurement validation is still intentionally minimal

- [ ] **Step 2: Append a new handoff entry to the Spec 15.2 file**

Append a new section under `## 10. 交接记录` describing:

- what changed in backend generation/validation wiring
- what changed in playback rebuild UI
- which tests were run
- unresolved issues and the recommended next step

- [ ] **Step 3: Re-read the updated docs for consistency**

Make sure the checklist and spec handoff say the same thing about:

- what is done
- what remains
- how the system currently decides failed-only rebuild targets

## Spec Coverage Check

This plan covers the remaining open requirements from `spec-15.2-slides-runtime-hardening-and-cost-control.md` as follows:

- `5.2 HTML 画布契约`: Task 2 and Task 4
- `5.3 页面合规 gate`: Task 1, Task 2, and Task 3
- `5.4 调试成本治理`: Task 5 and Task 6
- real failed-only / page-scoped rebuild verification: Task 6 and Task 7
- final verification expectation: Task 8
- required doc updates from section 9 of the spec: Task 9

Already completed requirements from the current spec handoff are intentionally not replanned here.

## Notes For Execution

- Prefer the smallest correct change at each step; do not redesign the slides pipeline.
- Preserve existing API schema and reuse fields already exposed by `/api/assets/{asset_id}/slides`.
- TDD still applies: write or extend the failing test first, verify the failure, then implement the minimum code to pass.
- When a verification step cannot be completed because the local stack is unavailable, record the exact blocker instead of silently skipping the step.
