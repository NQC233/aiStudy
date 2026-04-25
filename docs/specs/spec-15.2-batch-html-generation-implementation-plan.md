# Spec 15.2 Batch HTML Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace first-pass per-page HTML generation with deck-aware batch HTML generation while preserving page-level validation, runtime bundle semantics, and page-scoped rebuild paths.

**Architecture:** Keep `generate_asset_slides_runtime_bundle(...)` in [backend/app/services/slide_generation_v2_service.py](backend/app/services/slide_generation_v2_service.py) as the single orchestration entrypoint. Add a deck-aware batch HTML seam in [backend/app/services/slide_html_authoring_service.py](backend/app/services/slide_html_authoring_service.py) backed by a new LLM helper in [backend/app/services/llm_service.py](backend/app/services/llm_service.py), then persist `deck_meta` and batch generation observability inside `runtime_bundle` so page-level validation and rebuild can keep using the existing `rendered_slide_pages[] -> runtime_bundle` flow.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Python unittest/pytest, DashScope-compatible LLM JSON calls.

---

## File Structure

**Orchestration and runtime contract**
- Modify: `backend/app/services/slide_generation_v2_service.py` — switch full generation HTML path to batch mode; persist `deck_meta` and batch generation meta in `runtime_bundle`; enforce failed-only threshold; keep page rebuild on the existing page-local seam.
- Modify: `backend/app/services/slide_runtime_bundle_service.py` — preserve bundle summary semantics while allowing extra `deck_meta` / `generation_meta` fields to remain attached.
- Modify: `backend/app/schemas/slide_dsl.py` — extend `SlidesRuntimeBundle` with batch HTML metadata fields so API responses stay typed.

**HTML authoring**
- Modify: `backend/app/services/slide_html_authoring_service.py` — add `render_slide_pages_batch(...)`, chunking helper, bundle fallback, and page extraction back into `rendered_slide_pages[]`.
- Modify: `backend/app/services/llm_service.py` — add batch HTML prompt/response helper `generate_slide_html_bundle(...)` while keeping `generate_slide_html_page(...)` for rebuild paths.

**Configuration and docs**
- Modify: `backend/app/core/config.py` — add batch timeout / chunk / failed-only ratio settings.
- Modify: `.env.example` — declare new `SLIDES_HTML_BATCH_*` and `SLIDES_HTML_FAILED_ONLY_MAX_RATIO` variables.
- Modify: `README.md` — document the new batch HTML runtime controls.
- Modify: `docs/checklist.md` — record factual completion status and verification.
- Modify: `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md` — append handoff entry for the new HTML strategy.

**Tests**
- Modify: `backend/tests/test_llm_service.py`
- Modify: `backend/tests/test_slide_html_authoring_service.py`
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Modify: `backend/tests/test_runtime_config.py`

## Shared Invariants

Every task below must preserve these invariants:

- `rendered_slide_pages[]` remains the page-level source of truth for validation and runtime summary.
- `runtime_bundle.pages[]` remains page-based; do not replace it with a single long-document HTML payload.
- Existing rebuild payloads stay unchanged:
  - `{ from_stage: 'html', page_numbers: [n] }`
  - `{ from_stage: 'html', failed_only: true }`
- Full generation uses batch HTML; page-scoped rebuilds continue to use page-local HTML generation.
- `deck_meta` is authoritative for batch-level style consistency and must be reused by page rebuild paths.

### Task 1: Add Batch HTML Config And Runtime Bundle Contract

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/schemas/slide_dsl.py`
- Modify: `backend/tests/test_runtime_config.py`
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Test: `backend/tests/test_runtime_config.py`
- Test: `backend/tests/test_slide_generation_v2_service.py`

- [ ] **Step 1: Write the failing config test for batch HTML defaults**

Add a config regression test in `backend/tests/test_runtime_config.py`:

```python
class RuntimeConfigTests(unittest.TestCase):
    def test_default_slides_batch_html_settings_are_present(self) -> None:
        settings = Settings(_env_file=None)

        self.assertEqual(settings.slides_html_batch_timeout_sec, 600)
        self.assertEqual(settings.slides_html_batch_max_pages, 12)
        self.assertEqual(settings.slides_html_batch_chunk_size, 4)
        self.assertEqual(settings.slides_html_rebuild_timeout_sec, 180)
        self.assertEqual(settings.slides_html_failed_only_max_ratio, 0.3)
```

- [ ] **Step 2: Run the config test and verify it fails**

Run: `cd backend && python -m unittest tests.test_runtime_config.RuntimeConfigTests.test_default_slides_batch_html_settings_are_present -v`
Expected: FAIL with `AttributeError` on one or more missing `slides_html_batch_*` settings.

- [ ] **Step 3: Add the new settings in `config.py`**

Add these fields to `Settings` in `backend/app/core/config.py` near the existing `SLIDES_HTML_*` block:

```python
slides_html_batch_timeout_sec: int = 600
slides_html_batch_max_pages: int = 12
slides_html_batch_chunk_size: int = 4
slides_html_rebuild_timeout_sec: int = 180
slides_html_failed_only_max_ratio: float = 0.3
```

- [ ] **Step 4: Extend the runtime bundle schema with batch metadata**

Update `SlidesRuntimeBundle` in `backend/app/schemas/slide_dsl.py`:

```python
class SlidesRuntimeBundle(BaseModel):
    page_count: int = 0
    pages: list[RuntimeRenderedPage] = Field(default_factory=list)
    playable_page_count: int = 0
    failed_page_numbers: list[int] = Field(default_factory=list)
    validation_summary: SlidesRuntimeBundleValidationSummary = Field(
        default_factory=SlidesRuntimeBundleValidationSummary
    )
    deck_meta: dict[str, Any] = Field(default_factory=dict)
    generation_meta: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 5: Write the failing runtime bundle schema test**

Add a focused assertion in `backend/tests/test_slide_generation_v2_service.py`:

```python
def test_runtime_bundle_schema_accepts_batch_metadata(self) -> None:
    bundle = SlidesRuntimeBundle.model_validate(
        {
            "page_count": 1,
            "pages": [],
            "playable_page_count": 0,
            "failed_page_numbers": [],
            "validation_summary": {"status": "not_ready"},
            "deck_meta": {"typography": {"title_scale": 42}},
            "generation_meta": {"html_generation_mode": "batch", "html_batch_count": 1},
        }
    )

    assert bundle.deck_meta["typography"]["title_scale"] == 42
    assert bundle.generation_meta["html_generation_mode"] == "batch"
```

- [ ] **Step 6: Run the targeted tests and verify they pass**

Run: `cd backend && python -m unittest tests.test_runtime_config tests.test_slide_generation_v2_service -v`
Expected: PASS for the new config and schema assertions.

### Task 2: Add Deck-Aware Batch HTML LLM Helper

**Files:**
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/tests/test_llm_service.py`
- Test: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the failing LLM contract tests for batch HTML generation**

Add tests like these to `backend/tests/test_llm_service.py`:

```python
def test_generate_slide_html_bundle_normalizes_batch_output(self) -> None:
    bundle = generate_slide_html_bundle(
        scene_specs=[{"page_id": "page-1", "title": "问题背景"}],
        deck_style_guide={"theme_name": "paper-academic"},
        deck_digest={"page_roles": ["problem"]},
        model_caller=lambda _prompt, _payload: {
            "deck_meta": {
                "typography": {"title_scale": 42},
                "spacing": {"page_padding_x": 88},
            },
            "pages": [
                {
                    "page_id": "page-1",
                    "html": "<section>问题背景</section>",
                    "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }",
                    "render_meta": {"layout_family": "hero-text"},
                }
            ],
        },
    )

    self.assertEqual(bundle["deck_meta"]["typography"]["title_scale"], 42)
    self.assertEqual(bundle["pages"][0]["page_id"], "page-1")


def test_generate_slide_html_bundle_prompt_requires_single_batch_deck_output(self) -> None:
    captured_prompt: dict[str, str] = {}

    generate_slide_html_bundle(
        scene_specs=[{"page_id": "page-1", "title": "问题背景"}],
        deck_style_guide={"theme_name": "paper-academic"},
        deck_digest={"page_roles": ["problem"]},
        model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
            "deck_meta": {},
            "pages": [],
        },
    )

    self.assertIn("整套", captured_prompt["prompt"])
    self.assertIn("pages", captured_prompt["prompt"])
    self.assertIn("deck_meta", captured_prompt["prompt"])
    self.assertIn("固定", captured_prompt["prompt"])
    self.assertIn("不要返回长文档", captured_prompt["prompt"])
```

- [ ] **Step 2: Run the failing LLM tests**

Run: `cd backend && python -m unittest tests.test_llm_service -k slide_html_bundle -v`
Expected: FAIL because `generate_slide_html_bundle(...)` does not exist yet.

- [ ] **Step 3: Implement the minimal batch HTML LLM helper**

Add a new helper in `backend/app/services/llm_service.py`:

```python
def generate_slide_html_bundle(
    scene_specs: list[dict[str, Any]],
    *,
    deck_style_guide: dict[str, Any] | None = None,
    deck_digest: dict[str, Any] | None = None,
    deck_meta: dict[str, Any] | None = None,
    model_caller: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    canvas_width = settings.slides_html_canvas_width
    canvas_height = settings.slides_html_canvas_height
    raw = _call_slides_json_model(
        task_name="html",
        system_prompt=(
            "你负责一次性渲染整套多页 HTML 演示稿。只返回 JSON，顶层必须包含 deck_meta 和 pages。"
            "pages 必须是逐页数组；不要返回长文档，不要把整套内容拼成一个连续页面。"
            f"所有页面都必须遵守固定 {canvas_width}px × {canvas_height}px 画布、无滚动、安全区一致、主题一致。"
            "同一套 deck 的标题层级、正文密度、间距、引用样式必须统一。"
        ),
        user_payload={
            "scene_specs": scene_specs,
            "deck_style_guide": deck_style_guide or {},
            "deck_digest": deck_digest or {},
            "deck_meta": deck_meta or {},
        },
        model_caller=model_caller,
    )
    pages = raw.get("pages") if isinstance(raw.get("pages"), list) else []
    return {
        "deck_meta": raw.get("deck_meta") if isinstance(raw.get("deck_meta"), dict) else {},
        "pages": [
            {
                "page_id": str(page.get("page_id", f"page-{index}")),
                "html": str(page.get("html", "")).strip(),
                "css": str(page.get("css", "")).strip(),
                "render_meta": page.get("render_meta") if isinstance(page.get("render_meta"), dict) else {},
            }
            for index, page in enumerate(pages, start=1)
            if isinstance(page, dict)
        ],
    }
```

- [ ] **Step 4: Run the LLM service tests again**

Run: `cd backend && python -m unittest tests.test_llm_service -v`
Expected: PASS including the new `generate_slide_html_bundle(...)` tests.

### Task 3: Add Batch HTML Authoring Seam And Chunking

**Files:**
- Modify: `backend/app/services/slide_html_authoring_service.py`
- Modify: `backend/tests/test_slide_html_authoring_service.py`
- Test: `backend/tests/test_slide_html_authoring_service.py`

- [ ] **Step 1: Write the failing batch authoring tests**

Add these tests to `backend/tests/test_slide_html_authoring_service.py`:

```python
def test_render_slide_pages_batch_returns_page_level_pages_and_deck_meta(self) -> None:
    scene_specs = [
        {"page_id": "page-1", "title": "问题背景", "summary_line": "A"},
        {"page_id": "page-2", "title": "方法概览", "summary_line": "B"},
    ]

    result = render_slide_pages_batch(
        scene_specs,
        deck_style_guide={"theme_name": "paper-academic"},
        batch_html_writer=lambda scene_specs, **_kwargs: {
            "deck_meta": {"typography": {"title_scale": 42}},
            "pages": [
                {"page_id": scene_specs[0]["page_id"], "html": "<section>问题背景</section>", "css": ".page{}", "render_meta": {}},
                {"page_id": scene_specs[1]["page_id"], "html": "<section>方法概览</section>", "css": ".page{}", "render_meta": {}},
            ],
        },
    )

    self.assertEqual(result["deck_meta"]["typography"]["title_scale"], 42)
    self.assertEqual([page["page_id"] for page in result["pages"]], ["page-1", "page-2"])


def test_render_slide_pages_batch_chunks_large_deck_and_reuses_first_chunk_deck_meta(self) -> None:
    seen_inputs: list[dict[str, object]] = []
    scene_specs = [
        {"page_id": "page-1", "title": "1", "summary_line": "1"},
        {"page_id": "page-2", "title": "2", "summary_line": "2"},
        {"page_id": "page-3", "title": "3", "summary_line": "3"},
    ]

    def fake_batch_writer(scene_specs, deck_meta=None, **_kwargs):
        seen_inputs.append({"page_ids": [item["page_id"] for item in scene_specs], "deck_meta": deck_meta or {}})
        return {
            "deck_meta": deck_meta or {"typography": {"title_scale": 42}},
            "pages": [
                {"page_id": item["page_id"], "html": f"<section>{item['title']}</section>", "css": ".page{}", "render_meta": {}}
                for item in scene_specs
            ],
        }

    result = render_slide_pages_batch(
        scene_specs,
        deck_style_guide={"theme_name": "paper-academic"},
        batch_html_writer=fake_batch_writer,
        max_batch_pages=2,
        chunk_size=2,
    )

    self.assertEqual(seen_inputs[0]["page_ids"], ["page-1", "page-2"])
    self.assertEqual(seen_inputs[1]["page_ids"], ["page-3"])
    self.assertEqual(seen_inputs[1]["deck_meta"], {"typography": {"title_scale": 42}})
    self.assertEqual(len(result["pages"]), 3)
```

- [ ] **Step 2: Run the failing batch authoring tests**

Run: `cd backend && python -m unittest tests.test_slide_html_authoring_service -v`
Expected: FAIL because `render_slide_pages_batch(...)` does not exist.

- [ ] **Step 3: Implement the batch authoring seam**

Add these helpers to `backend/app/services/slide_html_authoring_service.py`:

```python
def _chunk_scene_specs(scene_specs: list[dict[str, object]], chunk_size: int) -> list[list[dict[str, object]]]:
    size = max(1, int(chunk_size or 1))
    return [scene_specs[index : index + size] for index in range(0, len(scene_specs), size)]


def _default_batch_html_writer(
    scene_specs: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, object] | None = None,
    deck_digest: dict[str, object] | None = None,
    deck_meta: dict[str, object] | None = None,
) -> dict[str, object]:
    pages = [render_slide_page(scene_spec, deck_style_guide=deck_style_guide) for scene_spec in scene_specs]
    return {
        "deck_meta": deck_meta or {
            "theme_name": (deck_style_guide or {}).get("theme_name", "paper-academic"),
        },
        "pages": pages,
    }


def render_slide_pages_batch(
    scene_specs: list[dict[str, object]],
    *,
    deck_style_guide: dict[str, object] | None = None,
    deck_digest: dict[str, object] | None = None,
    batch_html_writer: Callable[..., dict[str, object]] = _default_batch_html_writer,
    max_batch_pages: int = 12,
    chunk_size: int = 4,
) -> dict[str, object]:
    if len(scene_specs) <= max(1, int(max_batch_pages or 1)):
        return batch_html_writer(
            scene_specs,
            deck_style_guide=deck_style_guide,
            deck_digest=deck_digest or {},
            deck_meta=None,
        )

    bundle_pages: list[dict[str, object]] = []
    shared_deck_meta: dict[str, object] = {}
    for chunk in _chunk_scene_specs(scene_specs, chunk_size):
        chunk_bundle = batch_html_writer(
            chunk,
            deck_style_guide=deck_style_guide,
            deck_digest=deck_digest or {},
            deck_meta=shared_deck_meta or None,
        )
        if not shared_deck_meta and isinstance(chunk_bundle.get("deck_meta"), dict):
            shared_deck_meta = chunk_bundle["deck_meta"]
        bundle_pages.extend(chunk_bundle.get("pages") if isinstance(chunk_bundle.get("pages"), list) else [])
    return {
        "deck_meta": shared_deck_meta,
        "pages": bundle_pages,
    }
```

- [ ] **Step 4: Run the HTML authoring tests again**

Run: `cd backend && python -m unittest tests.test_slide_html_authoring_service -v`
Expected: PASS including the new batch seam coverage.

### Task 4: Switch Full Generation To Batch HTML And Persist Batch Metadata

**Files:**
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Test: `backend/tests/test_slide_generation_v2_service.py`

- [ ] **Step 1: Write the failing orchestration test for full-generation batch HTML**

Add a focused test to `backend/tests/test_slide_generation_v2_service.py`:

```python
def test_generate_asset_slides_runtime_bundle_uses_batch_html_for_full_generation(self) -> None:
    asset = SimpleNamespace(id="asset-1", title="Attention", slides_status="not_generated")
    presentation = SimpleNamespace(
        asset_id="asset-1",
        status="pending",
        runtime_bundle={},
        analysis_pack=None,
        visual_asset_catalog=None,
        presentation_plan=None,
        scene_specs=None,
        rendered_slide_pages=None,
        error_meta={},
        tts_manifest={},
        playback_plan={},
    )
    batch_calls: list[list[str]] = []

    result = generate_asset_slides_runtime_bundle(
        _FakeDb(asset, presentation),
        asset_id="asset-1",
        parsed_payload={"blocks": [], "assets": {"images": [], "tables": []}},
        analysis_builder=lambda *_args, **_kwargs: {"problem_statements": ["A"]},
        visual_asset_builder=lambda *_args, **_kwargs: [],
        plan_builder=lambda *_args, **_kwargs: {
            "page_count": 2,
            "pages": [
                {"page_id": "page-1", "scene_role": "problem", "narrative_goal": "A", "visual_strategy": "text_only"},
                {"page_id": "page-2", "scene_role": "method", "narrative_goal": "B", "visual_strategy": "text_only"},
            ],
        },
        scene_builder=lambda *_args, **_kwargs: [
            {"page_id": "page-1", "title": "问题", "summary_line": "A", "content_blocks": []},
            {"page_id": "page-2", "title": "方法", "summary_line": "B", "content_blocks": []},
        ],
        batch_html_renderer=lambda scene_specs, **_kwargs: batch_calls.append([item["page_id"] for item in scene_specs]) or {
            "deck_meta": {"typography": {"title_scale": 42}},
            "pages": [
                {"page_id": item["page_id"], "html": f"<section>{item['title']}</section>", "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }", "asset_refs": [], "render_meta": {}}
                for item in scene_specs
            ],
        },
        runtime_bundle_builder=build_runtime_bundle,
    )

    self.assertEqual(batch_calls, [["page-1", "page-2"]])
    self.assertEqual(result["runtime_bundle"]["deck_meta"]["typography"]["title_scale"], 42)
    self.assertEqual(result["runtime_bundle"]["generation_meta"]["html_generation_mode"], "batch")
```

- [ ] **Step 2: Run the failing orchestration test**

Run: `cd backend && python -m unittest tests.test_slide_generation_v2_service.SlideGenerationV2ServiceTests.test_generate_asset_slides_runtime_bundle_uses_batch_html_for_full_generation -v`
Expected: FAIL because `generate_asset_slides_runtime_bundle(...)` has no `batch_html_renderer` path.

- [ ] **Step 3: Add a batch HTML renderer seam to the orchestration service**

Update the imports in `backend/app/services/slide_generation_v2_service.py`:

```python
from app.services.slide_html_authoring_service import render_slide_pages_batch
```

Update the function signature:

```python
def generate_asset_slides_runtime_bundle(
    db: Session,
    *,
    ...,
    html_renderer: Callable[..., dict[str, object]] = render_slide_page,
    batch_html_renderer: Callable[..., dict[str, object]] = render_slide_pages_batch,
    ...,
) -> dict[str, Any]:
```

Replace the full-generation HTML branch with:

```python
html_bundle = batch_html_renderer(
    scene_specs,
    deck_style_guide=deck_style_guide,
    deck_digest={
        "page_roles": [str(page.get("scene_role", "")) for page in presentation_plan.get("pages", []) if isinstance(page, dict)],
        "page_count": len(scene_specs),
    },
    max_batch_pages=settings.slides_html_batch_max_pages,
    chunk_size=settings.slides_html_batch_chunk_size,
)
rendered_slide_pages = [_to_json_safe(page) for page in html_bundle.get("pages", []) if isinstance(page, dict)]
error_meta["html_generation"] = [
    {
        "status": "success",
        "reason": "",
        "mode": "batch_chunked" if len(scene_specs) > settings.slides_html_batch_max_pages else "batch",
        "page_count": len(rendered_slide_pages),
    }
]
runtime_bundle = finalize_rendered_slide_pages_for_runtime(
    rendered_slide_pages,
    canvas_width=settings.slides_html_canvas_width,
    canvas_height=settings.slides_html_canvas_height,
    validation_enabled=settings.slides_html_validation_enabled,
    validate_page_html=lambda **kwargs: build_slide_validation_result(
        enabled=settings.slides_html_validation_enabled,
        timeout_sec=settings.slides_html_validation_timeout_sec,
        **kwargs,
    ),
    runtime_bundle_builder=lambda pages: _to_json_safe(runtime_bundle_builder(pages)),
)
runtime_bundle["deck_meta"] = _to_json_safe(html_bundle.get("deck_meta") if isinstance(html_bundle.get("deck_meta"), dict) else {})
runtime_bundle["generation_meta"] = {
    "html_generation_mode": "batch_chunked" if len(scene_specs) > settings.slides_html_batch_max_pages else "batch",
    "html_batch_count": 1 if len(scene_specs) <= settings.slides_html_batch_max_pages else len(rendered_slide_pages),
    "html_batch_page_count": len(rendered_slide_pages),
}
```

- [ ] **Step 4: Run the generation service tests again**

Run: `cd backend && python -m unittest tests.test_slide_generation_v2_service -v`
Expected: PASS for the new batch-generation test and existing runtime bundle validation tests.

### Task 5: Reuse `deck_meta` For Rebuilds And Enforce Failed-Only Threshold

**Files:**
- Modify: `backend/app/services/slide_generation_v2_service.py`
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/tests/test_slide_generation_v2_service.py`
- Modify: `backend/tests/test_llm_service.py`
- Test: `backend/tests/test_slide_generation_v2_service.py`
- Test: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the failing tests for page rebuild style reuse and failed-only threshold**

Add these tests to `backend/tests/test_slide_generation_v2_service.py`:

```python
def test_page_scoped_html_rebuild_reuses_persisted_deck_meta(self) -> None:
    asset = SimpleNamespace(id="asset-1", title="Attention", slides_status="ready")
    presentation = SimpleNamespace(
        asset_id="asset-1",
        status="ready",
        runtime_bundle={
            "page_count": 2,
            "pages": [],
            "playable_page_count": 1,
            "failed_page_numbers": [2],
            "validation_summary": {"status": "partial_ready"},
            "deck_meta": {"typography": {"title_scale": 42}, "spacing": {"page_padding_x": 88}},
        },
        analysis_pack={"problem_statements": ["A"]},
        visual_asset_catalog=[],
        presentation_plan={
            "page_count": 2,
            "pages": [
                {"page_id": "page-1", "scene_role": "problem", "narrative_goal": "A", "visual_strategy": "text_only"},
                {"page_id": "page-2", "scene_role": "method", "narrative_goal": "B", "visual_strategy": "text_only"},
            ],
        },
        scene_specs=[
            {"page_id": "page-1", "title": "问题", "summary_line": "A", "content_blocks": []},
            {"page_id": "page-2", "title": "方法", "summary_line": "B", "content_blocks": []},
        ],
        rendered_slide_pages=[
            {"page_id": "page-1", "html": "<section>问题</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
            {"page_id": "page-2", "html": "<section>旧方法</section>", "css": ".page{}", "asset_refs": [], "render_meta": {}},
        ],
        error_meta={},
        tts_manifest={},
        playback_plan={},
    )
    seen_style_guides: list[dict[str, object]] = []

    generate_asset_slides_runtime_bundle(
        _FakeDb(asset, presentation),
        asset_id="asset-1",
        from_stage="html",
        page_numbers=[2],
        reuse_analysis_pack=True,
        reuse_presentation_plan=True,
        html_renderer=lambda scene_spec, deck_style_guide=None, **_kwargs: seen_style_guides.append(deck_style_guide) or {
            "page_id": scene_spec["page_id"],
            "html": "<section>新方法</section>",
            "css": "html, body { width: 1600px; height: 900px; overflow: hidden; }",
            "asset_refs": [],
            "render_meta": {},
        },
        runtime_bundle_builder=build_runtime_bundle,
    )

    self.assertEqual(seen_style_guides[0]["deck_meta"]["typography"]["title_scale"], 42)


def test_failed_only_rebuild_rejects_when_failed_ratio_exceeds_threshold(self) -> None:
    asset = SimpleNamespace(id="asset-1", title="Attention", slides_status="ready")
    presentation = SimpleNamespace(
        asset_id="asset-1",
        status="ready",
        runtime_bundle={
            "page_count": 4,
            "pages": [{}, {}, {}, {}],
            "playable_page_count": 2,
            "failed_page_numbers": [1, 2],
            "validation_summary": {"status": "partial_ready"},
            "deck_meta": {},
        },
        analysis_pack={"problem_statements": ["A"]},
        visual_asset_catalog=[],
        presentation_plan={"page_count": 4, "pages": [{"page_id": f"page-{index}"} for index in range(1, 5)]},
        scene_specs=[{"page_id": f"page-{index}", "title": str(index), "summary_line": str(index), "content_blocks": []} for index in range(1, 5)],
        rendered_slide_pages=[],
        error_meta={},
        tts_manifest={},
        playback_plan={},
    )

    with self.assertRaisesRegex(ValueError, "failed_only rebuild exceeds threshold"):
        generate_asset_slides_runtime_bundle(
            _FakeDb(asset, presentation),
            asset_id="asset-1",
            from_stage="html",
            failed_only=True,
            reuse_analysis_pack=True,
            reuse_presentation_plan=True,
        )
```

- [ ] **Step 2: Run the failing rebuild tests**

Run: `cd backend && python -m unittest tests.test_slide_generation_v2_service -k "reuses_persisted_deck_meta or exceeds_threshold" -v`
Expected: FAIL because rebuild currently does not inject `deck_meta` and does not gate failed-only by ratio.

- [ ] **Step 3: Implement `deck_meta` reuse and failed-only gating**

In `backend/app/services/slide_generation_v2_service.py`, add logic near the persisted runtime bundle setup:

```python
persisted_deck_meta = _coerce_persisted_dict(persisted_runtime_bundle.get("deck_meta"))
```

Add a helper:

```python
def _validate_failed_only_threshold(runtime_bundle: dict[str, Any], *, failed_page_numbers: list[int]) -> None:
    summary = summarize_runtime_bundle(runtime_bundle)
    page_count = max(1, int(summary["page_count"] or 0))
    failed_ratio = len(failed_page_numbers) / page_count
    if failed_ratio > settings.slides_html_failed_only_max_ratio:
        raise ValueError("failed_only rebuild exceeds threshold; rerun full generation")
```

Use it after resolving `effective_page_numbers`:

```python
if failed_only and effective_page_numbers:
    _validate_failed_only_threshold(
        persisted_runtime_bundle,
        failed_page_numbers=effective_page_numbers,
    )
```

Inject `deck_meta` into page-local HTML rebuild calls:

```python
deck_style_guide_with_meta = {
    **deck_style_guide,
    "deck_meta": persisted_deck_meta,
}
rendered_subset, html_meta = render_slide_pages(
    filtered_scene_specs,
    html_writer=active_html_renderer,
    parallelism=settings.slides_html_parallelism,
    deck_style_guide=deck_style_guide_with_meta,
)
```

- [ ] **Step 4: Make the single-page HTML prompt explicitly accept reused `deck_meta`**

In `backend/app/services/llm_service.py`, strengthen `generate_slide_html_page(...)` prompt and payload:

```python
user_payload={
    "scene_spec": scene_spec,
    "deck_style_guide": deck_style_guide or {},
    "deck_meta": (deck_style_guide or {}).get("deck_meta", {}),
}
```

And append to the system prompt:

```python
"如果提供了 deck_meta，你必须复用其中的 typography、spacing、tone、component rules，不得重新发明另一套风格。"
```

Add a test in `backend/tests/test_llm_service.py`:

```python
def test_generate_slide_html_page_prompt_mentions_deck_meta_reuse(self) -> None:
    captured_prompt: dict[str, str] = {}

    generate_slide_html_page(
        {"page_id": "page-1", "title": "问题背景", "summary_line": "A", "content_blocks": []},
        deck_style_guide={"deck_meta": {"typography": {"title_scale": 42}}},
        model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
            "html": "<section>问题背景</section>",
            "css": ".page{}",
            "render_meta": {},
        },
    )

    self.assertIn("deck_meta", captured_prompt["prompt"])
    self.assertIn("复用", captured_prompt["prompt"])
```

- [ ] **Step 5: Run the rebuild and LLM tests again**

Run: `cd backend && python -m unittest tests.test_slide_generation_v2_service tests.test_llm_service -v`
Expected: PASS for the new rebuild-style and threshold behavior.

### Task 6: Update Environment Docs And Record The Round

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md`

- [ ] **Step 1: Add the new settings to `.env.example`**

Add these variables under the existing `SLIDES_HTML_*` section in `.env.example`:

```dotenv
SLIDES_HTML_BATCH_TIMEOUT_SEC=600
SLIDES_HTML_BATCH_MAX_PAGES=12
SLIDES_HTML_BATCH_CHUNK_SIZE=4
SLIDES_HTML_REBUILD_TIMEOUT_SEC=180
SLIDES_HTML_FAILED_ONLY_MAX_RATIO=0.3
```

- [ ] **Step 2: Update `README.md` environment documentation**

Add the new variables to the slides configuration section, for example under `## 9. 环境变量与配置规范`:

```md
- `SLIDES_HTML_BATCH_TIMEOUT_SEC`：首轮 batch HTML 生成超时
- `SLIDES_HTML_BATCH_MAX_PAGES`：单次 batch 允许的最大页数；超过后改走 chunked batch
- `SLIDES_HTML_BATCH_CHUNK_SIZE`：chunked batch 的每批页数
- `SLIDES_HTML_REBUILD_TIMEOUT_SEC`：page rebuild / failed-only rebuild 超时
- `SLIDES_HTML_FAILED_ONLY_MAX_RATIO`：failed-only rebuild 允许的最大失败页占比，超过后应改走 full regeneration
```

- [ ] **Step 3: Update `docs/checklist.md` with factual status**

Append a new Spec 15.2 round entry covering:

```md
### Spec 15.2 本轮追加记录（Deck-Aware Batch HTML 首轮生成）

- 完成内容：
  - 首轮 full generation 的 HTML 主路径已从逐页 fan-out 切到 deck-aware batch generation
  - `runtime_bundle` 现可持久化 `deck_meta` 与 batch generation meta，供 failed-only / single-page rebuild 复用
  - page-level validation / failed-only rebuild payload 契约保持不变
  - failed-only rebuild 增加失败页占比阈值，超过阈值时要求重新 full generation
- 验证结果：
  - `cd backend && python -m unittest tests.test_runtime_config tests.test_llm_service tests.test_slide_html_authoring_service tests.test_slide_generation_v2_service -v` 通过
- 当前缺口：
  - batch prompt 仍需继续基于真实资产调优统一性与 token 体积
  - chunked batch 的 style drift 仍需观察
- 下一轮建议：
  - 用真实 8-12 页资产记录 batch vs 旧 per-page 的耗时与一致性对比
- 建议提交信息：
  - `feat: switch initial slide html generation to deck-aware batch mode`
```

- [ ] **Step 4: Append the Spec 15.2 handoff note**

Under `## 10. 交接记录` in `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md`, add a new section with:

```md
### 第 N 轮（Deck-Aware Batch HTML 首轮生成）

- 实际完成内容：
  - 首轮 full generation 改为 deck-aware batch HTML；page rebuild 仍保留 page-local 路径
  - `runtime_bundle.deck_meta` 成为 rebuild 复用的统一风格契约
  - 新增 batch timeout / chunk / failed-only threshold 配置
- 验证结果：
  - [列出本轮通过的 unittest 命令]
- 当前已知缺口：
  - [列出 batch prompt 与真实资产观测缺口]
- 下一轮建议：
  - [列出真实资产 benchmark 与 prompt 收敛方向]
```

- [ ] **Step 5: Re-read the updated docs for consistency**

Check that `.env.example`, `README.md`, `docs/checklist.md`, and `spec-15.2-slides-runtime-hardening-and-cost-control.md` all use the same variable names:

- `SLIDES_HTML_BATCH_TIMEOUT_SEC`
- `SLIDES_HTML_BATCH_MAX_PAGES`
- `SLIDES_HTML_BATCH_CHUNK_SIZE`
- `SLIDES_HTML_REBUILD_TIMEOUT_SEC`
- `SLIDES_HTML_FAILED_ONLY_MAX_RATIO`

### Task 7: Run Focused Verification

**Files:**
- No code changes required in this task

- [ ] **Step 1: Run backend unit tests for the modified seams**

Run:

```bash
cd backend && python -m unittest tests.test_runtime_config tests.test_llm_service tests.test_slide_html_authoring_service tests.test_slide_generation_v2_service -v
```

Expected: PASS.

- [ ] **Step 2: Run the full modified backend subset once more after doc updates**

Run:

```bash
cd backend && python -m unittest tests.test_slide_generation_v2_service -v
```

Expected: PASS.

- [ ] **Step 3: Record the exact commands and observed behavior in docs**

Make sure the `docs/checklist.md` and `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md` entries include the exact test commands that passed. If any command cannot be completed, record the blocker explicitly instead of silently omitting it.

## Spec Coverage Check

This plan covers [spec-15.2-batch-html-generation-design.md](docs/specs/spec-15.2-batch-html-generation-design.md) as follows:

- batch full generation as the authoritative first-pass HTML path: Task 2, Task 3, Task 4
- page-level artifacts and validation invariants preserved: Task 1, Task 4, Task 5
- rebuild reuse of `deck_meta`: Task 5
- failed-only ratio threshold and full-regeneration fallback: Task 1, Task 5
- timeout / chunk / observability configuration: Task 1, Task 3, Task 6
- authoritative docs updates: Task 6
- focused verification: Task 7

## Notes For Execution

- Do not remove the existing `generate_slide_html_page(...)` path; it remains the rebuild seam.
- Keep the rebuild API payload unchanged; all caller-facing changes should be internal or additive.
- Do not introduce fallback/default values to hide missing `deck_meta`; if a rebuild path expects it and it is absent, surface that explicitly in `error_meta` or raise a clear error.
- Prefer the smallest correct change: one new batch seam, one orchestration switch, one rebuild reuse path.
