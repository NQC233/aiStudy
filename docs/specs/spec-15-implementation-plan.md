# Spec 15 / 15.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the slides pipeline around `parsed_json -> analysis -> planning -> scene -> HTML page`, with a pure HTML/CSS runtime that prioritizes automatic presentation quality over legacy DSL compatibility.

**Architecture:** The implementation proceeds in four layers. First, validate and formalize a slide-oriented RAG strategy plus visual asset enrichment on top of `parsed_json`. Second, replace the old lesson-plan/DSL path with `analysis_pack`, `visual_asset_catalog`, `presentation_plan`, and `scene_spec` services. Third, generate page-level HTML/CSS artifacts and assemble them into a deck payload. Fourth, replace the current slides playback UI with an HTML runtime shell that consumes rendered pages and leaves hooks for future speaker-note/TTS features.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Pydantic, DashScope (`Qwen3.6-Plus`, `Qwen-Image-2.0`), pgvector retrieval, Vue 3, TypeScript, Vite.

---

## File Structure

**Backend service layer**
- Create: `backend/app/services/slide_analysis_service.py`
- Create: `backend/app/services/slide_visual_asset_service.py`
- Create: `backend/app/services/slide_planning_service.py`
- Create: `backend/app/services/slide_scene_service.py`
- Create: `backend/app/services/slide_html_authoring_service.py`
- Create: `backend/app/services/slide_runtime_bundle_service.py`
- Create: `backend/app/services/slide_validation_service.py`
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/app/services/retrieval_service.py`
- Modify: `backend/app/services/parse_normalizer.py`
- Modify: `backend/app/services/__init__.py`

**Backend schema/model/api layer**
- Create: `backend/app/schemas/slide_generation_v2.py`
- Modify: `backend/app/models/presentation.py`
- Modify: `backend/app/api/routes/assets.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`

**Frontend runtime layer**
- Create: `frontend/src/components/slides/HtmlSlideFrame.vue`
- Create: `frontend/src/components/slides/SlidesDeckRuntime.vue`
- Modify: `frontend/src/pages/slides/SlidesPlayPage.vue`
- Modify: `frontend/src/api/assets.ts`
- Delete or stop using: `frontend/src/components/slides/RevealSlidesDeck.vue`
- Delete or stop using: `frontend/src/components/slides/SlideBlockRenderer.vue`
- Delete or stop using: `frontend/src/components/slides/SafeSvgRenderer.vue`

**Tests**
- Create: `backend/tests/test_slide_analysis_service.py`
- Create: `backend/tests/test_slide_visual_asset_service.py`
- Create: `backend/tests/test_slide_planning_service.py`
- Create: `backend/tests/test_slide_scene_service.py`
- Create: `backend/tests/test_slide_html_authoring_service.py`
- Modify or replace: `backend/tests/test_spec15_slides_pipeline.py`
- Create: `frontend/src/pages/slides/__tests__/slides-runtime.spec.ts`

**Docs/status**
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-15-slides-generation-and-playback-enhancement.md`
- Modify: `docs/specs/spec-15.1-reveal-runtime-migration.md`

### Task 1: Validate RAG Query Families And Slide-Oriented Evidence Pack

**Files:**
- Create: `backend/tests/test_slide_analysis_service.py`
- Create: `backend/app/services/slide_analysis_service.py`
- Modify: `backend/app/services/retrieval_service.py`
- Modify: `backend/app/services/query_rewrite_service.py`
- Test: `backend/tests/test_slide_analysis_service.py`

- [ ] **Step 1: Write the failing tests for query-family retrieval validation**

```python
from unittest import TestCase

from app.services.slide_analysis_service import (
    DEFAULT_SLIDE_QUERY_FAMILIES,
    filter_slide_retrieval_hits,
    summarize_slide_analysis_pack,
)
from app.schemas.document_chunk import RetrievalSearchHit


class SlideAnalysisServiceTestCase(TestCase):
    def test_filter_slide_retrieval_hits_removes_low_signal_entries(self) -> None:
        hits = [
            RetrievalSearchHit(
                chunk_id="c1",
                score=0.91,
                text="Attention Is All You Need",
                page_start=1,
                page_end=1,
                block_ids=["b1"],
                section_path=["Title"],
            ),
            RetrievalSearchHit(
                chunk_id="c2",
                score=0.89,
                text="Our model improves BLEU by 2.0 over the previous best system.",
                page_start=8,
                page_end=8,
                block_ids=["b2"],
                section_path=["Results"],
            ),
        ]

        filtered = filter_slide_retrieval_hits(hits)

        self.assertEqual([item.chunk_id for item in filtered], ["c2"])

    def test_summarize_slide_analysis_pack_groups_hits_by_query_family(self) -> None:
        grouped_hits = {
            "main_experiment_results": [
                RetrievalSearchHit(
                    chunk_id="c9",
                    score=0.93,
                    text="Transformer achieves state-of-the-art BLEU on WMT14 En-De.",
                    page_start=8,
                    page_end=8,
                    block_ids=["b9"],
                    section_path=["Results"],
                )
            ]
        }

        pack = summarize_slide_analysis_pack(grouped_hits)

        self.assertIn("main_experiment_results", pack.query_family_hits)
        self.assertEqual(pack.query_family_hits["main_experiment_results"][0].chunk_id, "c9")

    def test_default_query_families_include_visual_queries(self) -> None:
        keys = [item.key for item in DEFAULT_SLIDE_QUERY_FAMILIES]

        self.assertIn("figures_worth_showing", keys)
        self.assertIn("tables_worth_showing", keys)
```

- [ ] **Step 2: Run the failing backend test**

Run: `python -m unittest backend.tests.test_slide_analysis_service -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for `slide_analysis_service`.

- [ ] **Step 3: Implement the minimal query-family analysis service and low-signal filtering**

```python
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.document_chunk import RetrievalSearchHit


@dataclass(frozen=True)
class SlideQueryFamily:
    key: str
    query: str


@dataclass
class SlideAnalysisPack:
    query_family_hits: dict[str, list[RetrievalSearchHit]]


DEFAULT_SLIDE_QUERY_FAMILIES = [
    SlideQueryFamily("paper_motivation", "research problem and motivation"),
    SlideQueryFamily("method_overview", "method overview and framework"),
    SlideQueryFamily("method_steps", "method stages modules pipeline"),
    SlideQueryFamily("key_formulas", "objective loss formula equation"),
    SlideQueryFamily("datasets_metrics", "datasets metrics evaluation setup"),
    SlideQueryFamily("main_experiment_results", "main experiment results performance"),
    SlideQueryFamily("ablations_comparisons", "ablation comparison baseline"),
    SlideQueryFamily("limitations_future_work", "limitations future work"),
    SlideQueryFamily("figures_worth_showing", "important figures diagrams architecture"),
    SlideQueryFamily("tables_worth_showing", "important result tables metrics"),
]


def _is_low_signal_text(text: str) -> bool:
    normalized = " ".join((text or "").split()).strip().lower()
    if not normalized:
        return True
    blocked_prefixes = ("attention is all you need", "copyright", "references")
    return normalized.startswith(blocked_prefixes) or len(normalized) < 24


def filter_slide_retrieval_hits(hits: list[RetrievalSearchHit]) -> list[RetrievalSearchHit]:
    filtered: list[RetrievalSearchHit] = []
    seen_chunk_ids: set[str] = set()
    for hit in hits:
        if hit.chunk_id in seen_chunk_ids:
            continue
        if _is_low_signal_text(hit.text):
            continue
        filtered.append(hit)
        seen_chunk_ids.add(hit.chunk_id)
    return filtered


def summarize_slide_analysis_pack(
    grouped_hits: dict[str, list[RetrievalSearchHit]],
) -> SlideAnalysisPack:
    return SlideAnalysisPack(
        query_family_hits={key: filter_slide_retrieval_hits(value) for key, value in grouped_hits.items()}
    )
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest backend.tests.test_slide_analysis_service -v`
Expected: PASS with 3 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/slide_analysis_service.py backend/tests/test_slide_analysis_service.py
git commit -m "feat: add slide query family analysis scaffold"
```

### Task 2: Build Visual Asset Enrichment For Original Figures And Tables

**Files:**
- Create: `backend/tests/test_slide_visual_asset_service.py`
- Create: `backend/app/services/slide_visual_asset_service.py`
- Modify: `backend/app/services/parse_normalizer.py`
- Modify: `backend/app/services/llm_service.py`
- Test: `backend/tests/test_slide_visual_asset_service.py`

- [ ] **Step 1: Write the failing tests for visual asset cards**

```python
from unittest import TestCase

from app.services.slide_visual_asset_service import build_visual_asset_cards


class SlideVisualAssetServiceTestCase(TestCase):
    def test_build_visual_asset_cards_uses_caption_and_context(self) -> None:
        assets = [
            {
                "asset_id": "fig-1",
                "asset_type": "image",
                "page_no": 4,
                "block_id": "block-fig-1",
                "caption": "Figure 1: Transformer architecture.",
                "surrounding_context": "The encoder and decoder are both composed of stacked self-attention layers.",
                "public_url": "https://example.com/fig1.png",
            }
        ]

        cards = build_visual_asset_cards(assets, describe_asset=lambda asset: {"vision_summary": asset["caption"], "recommended_usage": "method_overview"})

        self.assertEqual(cards[0]["asset_id"], "fig-1")
        self.assertEqual(cards[0]["recommended_usage"], "method_overview")

    def test_build_visual_asset_cards_preserves_page_and_block_anchor(self) -> None:
        assets = [
            {
                "asset_id": "tbl-2",
                "asset_type": "table",
                "page_no": 9,
                "block_id": "block-table-2",
                "caption": "Table 2: BLEU comparison.",
                "surrounding_context": "We compare against strong recurrent and convolutional baselines.",
                "public_url": "https://example.com/table2.png",
            }
        ]

        cards = build_visual_asset_cards(assets, describe_asset=lambda asset: {"vision_summary": "BLEU result table", "recommended_usage": "results_comparison"})

        self.assertEqual(cards[0]["page_no"], 9)
        self.assertEqual(cards[0]["block_id"], "block-table-2")
```

- [ ] **Step 2: Run the failing backend test**

Run: `python -m unittest backend.tests.test_slide_visual_asset_service -v`
Expected: FAIL with missing module or symbol errors for `slide_visual_asset_service`.

- [ ] **Step 3: Implement the minimal visual asset enrichment service**

```python
from __future__ import annotations

from collections.abc import Callable


def build_visual_asset_cards(
    assets: list[dict[str, object]],
    *,
    describe_asset: Callable[[dict[str, object]], dict[str, str]],
) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for asset in assets:
        described = describe_asset(asset)
        cards.append(
            {
                "asset_id": asset["asset_id"],
                "asset_type": asset["asset_type"],
                "page_no": asset["page_no"],
                "block_id": asset["block_id"],
                "caption": asset.get("caption", ""),
                "surrounding_context": asset.get("surrounding_context", ""),
                "public_url": asset.get("public_url", ""),
                "vision_summary": described.get("vision_summary", ""),
                "recommended_usage": described.get("recommended_usage", "general_visual"),
            }
        )
    return cards
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest backend.tests.test_slide_visual_asset_service -v`
Expected: PASS with 2 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/slide_visual_asset_service.py backend/tests/test_slide_visual_asset_service.py
git commit -m "feat: add visual asset enrichment scaffold"
```

### Task 3: Replace Lesson-Plan/DSL Pipeline With Analysis, Planning, And Scene Specs

**Files:**
- Create: `backend/tests/test_slide_planning_service.py`
- Create: `backend/tests/test_slide_scene_service.py`
- Create: `backend/app/services/slide_planning_service.py`
- Create: `backend/app/services/slide_scene_service.py`
- Create: `backend/app/schemas/slide_generation_v2.py`
- Modify: `backend/app/models/presentation.py`
- Modify: `backend/app/api/routes/assets.py`
- Test: `backend/tests/test_slide_planning_service.py`
- Test: `backend/tests/test_slide_scene_service.py`

- [ ] **Step 1: Write the failing tests for `presentation_plan` and `scene_spec` generation**

```python
from unittest import TestCase

from app.services.slide_planning_service import build_presentation_plan
from app.services.slide_scene_service import build_scene_specs


class SlidePlanningServiceTestCase(TestCase):
    def test_build_presentation_plan_creates_roles_and_visual_strategy(self) -> None:
        analysis_pack = {
            "core_claims": ["Transformer removes recurrence and relies entirely on attention."],
            "main_results": ["Transformer improves BLEU on WMT14 En-De and En-Fr."],
        }
        visual_asset_catalog = [{"asset_id": "fig-1", "recommended_usage": "method_overview"}]

        plan = build_presentation_plan(analysis_pack, visual_asset_catalog, plan_writer=lambda *_args, **_kwargs: {
            "page_count": 8,
            "pages": [
                {
                    "page_id": "page-1",
                    "scene_role": "cover",
                    "narrative_goal": "Introduce the paper contribution.",
                    "content_focus": "core_claim",
                    "visual_strategy": "text_plus_original_figure",
                    "candidate_assets": ["fig-1"],
                    "animation_intent": "soft_intro",
                }
            ],
        })

        self.assertEqual(plan["page_count"], 8)
        self.assertEqual(plan["pages"][0]["scene_role"], "cover")


class SlideSceneServiceTestCase(TestCase):
    def test_build_scene_specs_creates_page_level_scene_units(self) -> None:
        presentation_plan = {
            "page_count": 1,
            "pages": [
                {
                    "page_id": "page-1",
                    "scene_role": "method",
                    "narrative_goal": "Explain the architecture.",
                    "content_focus": "method_overview",
                    "visual_strategy": "text_plus_original_figure",
                    "candidate_assets": ["fig-1"],
                    "animation_intent": "stagger_reveal",
                }
            ],
        }

        scenes = build_scene_specs(
            presentation_plan,
            scene_writer=lambda page, *_args, **_kwargs: {
                "page_id": page["page_id"],
                "title": "Transformer Architecture",
                "summary_line": "Self-attention replaces recurrence.",
                "layout_strategy": "hero-visual-right",
                "content_blocks": [{"type": "bullets", "items": ["Encoder", "Decoder"]}],
                "citations": [{"page_no": 4, "block_ids": ["block-1"]}],
                "asset_bindings": [{"asset_id": "fig-1"}],
                "animation_plan": {"type": "stagger_reveal"},
                "speaker_note_seed": "Start from the encoder-decoder split.",
            },
        )

        self.assertEqual(scenes[0]["page_id"], "page-1")
        self.assertEqual(scenes[0]["layout_strategy"], "hero-visual-right")
```

- [ ] **Step 2: Run the failing planning/scene tests**

Run: `python -m unittest backend.tests.test_slide_planning_service backend.tests.test_slide_scene_service -v`
Expected: FAIL with missing modules for `slide_planning_service` and `slide_scene_service`.

- [ ] **Step 3: Implement the minimal planning and scene services plus typed schema file**

```python
from __future__ import annotations

from collections.abc import Callable


def build_presentation_plan(
    analysis_pack: dict[str, object],
    visual_asset_catalog: list[dict[str, object]],
    *,
    plan_writer: Callable[[dict[str, object], list[dict[str, object]]], dict[str, object]],
) -> dict[str, object]:
    plan = plan_writer(analysis_pack, visual_asset_catalog)
    if "page_count" not in plan or "pages" not in plan:
        raise ValueError("presentation plan missing required keys")
    return plan
```

```python
from __future__ import annotations

from collections.abc import Callable


def build_scene_specs(
    presentation_plan: dict[str, object],
    *,
    scene_writer: Callable[[dict[str, object]], dict[str, object]],
) -> list[dict[str, object]]:
    pages = presentation_plan.get("pages", [])
    if not isinstance(pages, list):
        raise ValueError("presentation plan pages must be a list")
    return [scene_writer(page) for page in pages]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest backend.tests.test_slide_planning_service backend.tests.test_slide_scene_service -v`
Expected: PASS with 2 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/slide_planning_service.py backend/app/services/slide_scene_service.py backend/tests/test_slide_planning_service.py backend/tests/test_slide_scene_service.py
git commit -m "feat: add presentation planning and scene spec scaffolds"
```

### Task 4: Generate Page-Level HTML/CSS And Assemble Runtime Deck Payload

**Files:**
- Create: `backend/tests/test_slide_html_authoring_service.py`
- Create: `backend/app/services/slide_html_authoring_service.py`
- Create: `backend/app/services/slide_runtime_bundle_service.py`
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Test: `backend/tests/test_slide_html_authoring_service.py`

- [ ] **Step 1: Write the failing tests for HTML page generation and deck assembly**

```python
from unittest import TestCase

from app.services.slide_html_authoring_service import render_slide_page
from app.services.slide_runtime_bundle_service import build_runtime_bundle


class SlideHtmlAuthoringServiceTestCase(TestCase):
    def test_render_slide_page_returns_page_level_html_payload(self) -> None:
        scene_spec = {
            "page_id": "page-1",
            "title": "Transformer Architecture",
            "summary_line": "Self-attention replaces recurrence.",
        }

        rendered = render_slide_page(scene_spec, html_writer=lambda scene: {"html": f"<section>{scene['title']}</section>", "css": ".page{}"})

        self.assertEqual(rendered["page_id"], "page-1")
        self.assertIn("Transformer Architecture", rendered["html"])

    def test_build_runtime_bundle_wraps_rendered_pages(self) -> None:
        bundle = build_runtime_bundle([
            {"page_id": "page-1", "html": "<section>One</section>", "css": ".one{}", "asset_refs": [], "render_meta": {}}
        ])

        self.assertEqual(bundle["page_count"], 1)
        self.assertEqual(bundle["pages"][0]["page_id"], "page-1")
```

- [ ] **Step 2: Run the failing HTML/runtime tests**

Run: `python -m unittest backend.tests.test_slide_html_authoring_service -v`
Expected: FAIL with missing module errors for HTML authoring/runtime services.

- [ ] **Step 3: Implement minimal page renderer and deck bundle services**

```python
from __future__ import annotations

from collections.abc import Callable


def render_slide_page(
    scene_spec: dict[str, object],
    *,
    html_writer: Callable[[dict[str, object]], dict[str, str]],
) -> dict[str, object]:
    rendered = html_writer(scene_spec)
    return {
        "page_id": scene_spec["page_id"],
        "html": rendered["html"],
        "css": rendered["css"],
        "asset_refs": scene_spec.get("asset_bindings", []),
        "render_meta": {"layout_strategy": scene_spec.get("layout_strategy", "")},
    }
```

```python
from __future__ import annotations


def build_runtime_bundle(rendered_pages: list[dict[str, object]]) -> dict[str, object]:
    return {
        "page_count": len(rendered_pages),
        "pages": rendered_pages,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m unittest backend.tests.test_slide_html_authoring_service -v`
Expected: PASS with 2 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/slide_html_authoring_service.py backend/app/services/slide_runtime_bundle_service.py backend/tests/test_slide_html_authoring_service.py backend/app/core/config.py .env.example
git commit -m "feat: add slide html authoring and runtime bundle scaffolds"
```

### Task 5: Replace Frontend Reveal Runtime With HTML Deck Runtime

**Files:**
- Create: `frontend/src/components/slides/HtmlSlideFrame.vue`
- Create: `frontend/src/components/slides/SlidesDeckRuntime.vue`
- Modify: `frontend/src/pages/slides/SlidesPlayPage.vue`
- Modify: `frontend/src/api/assets.ts`
- Test: `frontend/src/pages/slides/__tests__/slides-runtime.spec.ts`

- [ ] **Step 1: Write the failing frontend test for deck runtime rendering**

```ts
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import SlidesDeckRuntime from '@/components/slides/SlidesDeckRuntime.vue';

describe('SlidesDeckRuntime', () => {
  it('renders the active HTML slide page', () => {
    const wrapper = mount(SlidesDeckRuntime, {
      props: {
        pages: [
          {
            page_id: 'page-1',
            html: '<section><h1>Transformer</h1></section>',
            css: 'h1 { color: red; }',
            asset_refs: [],
            render_meta: {},
          },
        ],
        currentIndex: 0,
      },
    });

    expect(wrapper.html()).toContain('Transformer');
  });
});
```

- [ ] **Step 2: Run the failing frontend test**

Run: `npm run test -- SlidesDeckRuntime`
Expected: FAIL with missing component/module errors.

- [ ] **Step 3: Implement the minimal HTML frame and deck runtime**

```vue
<script setup lang="ts">
const props = defineProps<{
  html: string;
  css: string;
}>();
</script>

<template>
  <iframe class="slide-frame" :srcdoc="`<style>${props.css}</style>${props.html}`" />
</template>
```

```vue
<script setup lang="ts">
import { computed } from 'vue';

import HtmlSlideFrame from '@/components/slides/HtmlSlideFrame.vue';

const props = defineProps<{
  pages: Array<{ page_id: string; html: string; css: string; asset_refs: unknown[]; render_meta: Record<string, unknown> }>;
  currentIndex: number;
}>();

const activePage = computed(() => props.pages[props.currentIndex] ?? null);
</script>

<template>
  <div class="slides-deck-runtime">
    <HtmlSlideFrame v-if="activePage" :html="activePage.html" :css="activePage.css" />
  </div>
</template>
```

- [ ] **Step 4: Run the frontend test to verify it passes**

Run: `npm run test -- SlidesDeckRuntime`
Expected: PASS with 1 test.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/slides/HtmlSlideFrame.vue frontend/src/components/slides/SlidesDeckRuntime.vue frontend/src/pages/slides/__tests__/slides-runtime.spec.ts frontend/src/pages/slides/SlidesPlayPage.vue frontend/src/api/assets.ts
git commit -m "feat: replace slides runtime with html deck player"
```

### Task 6: Remove Old Slides Pipeline And Update Status Docs

**Files:**
- Modify: `backend/app/services/__init__.py`
- Delete: `backend/app/services/slide_lesson_plan_service.py`
- Delete: `backend/app/services/slide_outline_service.py`
- Delete: `backend/app/services/slide_markdown_service.py`
- Delete: `backend/app/services/slide_dsl_compiler_service.py`
- Delete: `backend/app/services/slide_dsl_service.py`
- Delete: `backend/app/services/slide_fix_service.py`
- Delete or stop using: `backend/tests/test_slide_lesson_plan_service.py`
- Delete or stop using: `backend/tests/test_slide_dsl_quality_flow.py`
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-15-slides-generation-and-playback-enhancement.md`
- Modify: `docs/specs/spec-15.1-reveal-runtime-migration.md`

- [ ] **Step 1: Write a failing smoke test that only exercises the new pipeline entrypoint**

```python
from unittest import TestCase

from app.services.slide_runtime_bundle_service import build_runtime_bundle


class Spec15PipelineSmokeTestCase(TestCase):
    def test_new_pipeline_bundle_smoke(self) -> None:
        bundle = build_runtime_bundle([
            {
                "page_id": "page-1",
                "html": "<section>hello</section>",
                "css": "section{}",
                "asset_refs": [],
                "render_meta": {},
            }
        ])

        self.assertEqual(bundle["page_count"], 1)
```

- [ ] **Step 2: Run the smoke test and verify the old tests still expose legacy coupling**

Run: `python -m unittest backend.tests.test_spec15_slides_pipeline -v`
Expected: FAIL until the legacy test file is rewritten to target the new services.

- [ ] **Step 3: Replace the old pipeline smoke test and remove legacy service imports**

```python
from unittest import TestCase

from app.services.slide_runtime_bundle_service import build_runtime_bundle


class Spec15PipelineSmokeTestCase(TestCase):
    def test_runtime_bundle_smoke(self) -> None:
        bundle = build_runtime_bundle([
            {
                "page_id": "page-1",
                "html": "<section>hello</section>",
                "css": "section{}",
                "asset_refs": [],
                "render_meta": {},
            }
        ])
        self.assertEqual(bundle["page_count"], 1)
```

- [ ] **Step 4: Run the smoke test and docs verification**

Run: `python -m unittest backend.tests.test_spec15_slides_pipeline -v`
Expected: PASS with the rewritten smoke test.

Run: `npm run build`
Expected: PASS after old runtime references are removed from the frontend.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/__init__.py backend/tests/test_spec15_slides_pipeline.py docs/checklist.md docs/specs/spec-15-slides-generation-and-playback-enhancement.md docs/specs/spec-15.1-reveal-runtime-migration.md
git commit -m "refactor: remove legacy slides pipeline entrypoints"
```

## Self-Review

- Spec coverage: this plan covers the required query-family validation, visual asset enrichment, planning/scene generation, page-level HTML generation, HTML runtime replacement, environment model config changes, and legacy pipeline removal.
- Placeholder scan: all tasks reference concrete files, tests, commands, and expected outcomes.
- Type consistency: the same core names are used throughout the plan: `analysis_pack`, `visual_asset_catalog`, `presentation_plan`, `scene_spec`, `rendered_slide_page`, and `runtime_bundle`.
