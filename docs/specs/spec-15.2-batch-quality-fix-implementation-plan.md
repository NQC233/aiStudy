# Spec 15.2 Batch Quality Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen batch slide HTML generation so it matches the single-page canvas and content contract, then fix iframe rendering so fixed 1600x900 slides display without scrollbars in the playback shell.

**Architecture:** Keep this round tightly scoped to the two root-cause surfaces identified in Spec 15.2 round 14: batch prompt contract in the backend and fixed-canvas display in the frontend. Do not rebuild unrelated assets or touch broader slide-generation orchestration; use TDD on the backend prompt contract first, then make the smallest frontend rendering change that scales the existing fixed-canvas pages correctly.

**Tech Stack:** Python, unittest, Vue 3, TypeScript, Vite

---

### Task 1: Lock the batch prompt contract with failing backend tests

**Files:**
- Modify: `backend/tests/test_llm_service.py`
- Modify: `backend/app/services/llm_service.py`
- Test: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Write the failing test for fixed-canvas batch prompt requirements**

```python
    def test_generate_slide_html_bundle_prompt_requires_fixed_canvas_contract(self) -> None:
        captured_prompt: dict[str, str] = {}

        generate_slide_html_bundle(
            scene_specs=[{"page_id": "page-1", "title": "问题背景", "asset_bindings": [{"asset_id": "fig-1"}]}],
            deck_style_guide={"theme_name": "paper-academic"},
            deck_digest={"page_roles": ["problem"]},
            model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
                "deck_meta": {},
                "pages": [],
            },
        )

        self.assertIn("html、body", captured_prompt["prompt"])
        self.assertIn("1600px × 900px", captured_prompt["prompt"])
        self.assertIn("overflow: hidden", captured_prompt["prompt"])
        self.assertIn("禁止 body 滚动、根容器滚动、内部容器滚动", captured_prompt["prompt"])
        self.assertIn("安全区", captured_prompt["prompt"])
```

- [ ] **Step 2: Write the failing test for real asset rendering and markdown/formula landing requirements**

```python
    def test_generate_slide_html_bundle_prompt_requires_real_asset_rendering_and_final_html(self) -> None:
        captured_prompt: dict[str, str] = {}

        generate_slide_html_bundle(
            scene_specs=[{"page_id": "page-1", "title": "方法概览", "asset_bindings": [{"asset_id": "fig-1"}]}],
            deck_style_guide={"theme_name": "paper-academic"},
            deck_digest={"page_roles": ["method"]},
            model_caller=lambda prompt, _payload: captured_prompt.update({"prompt": prompt}) or {
                "deck_meta": {},
                "pages": [],
            },
        )

        self.assertIn("asset_bindings", captured_prompt["prompt"])
        self.assertIn("<img>", captured_prompt["prompt"])
        self.assertIn("<svg>", captured_prompt["prompt"])
        self.assertIn("<table>", captured_prompt["prompt"])
        self.assertIn("不得输出 placeholder", captured_prompt["prompt"])
        self.assertIn("Markdown", captured_prompt["prompt"])
        self.assertIn("公式", captured_prompt["prompt"])
        self.assertIn("最终 HTML", captured_prompt["prompt"])
```

- [ ] **Step 3: Run the focused backend tests and confirm they fail for the expected reason**

Run:
```bash
cd /Users/nqc233/VSCode/aiStudy/backend && python -m unittest tests.test_llm_service.LlmServiceTests.test_generate_slide_html_bundle_prompt_requires_fixed_canvas_contract tests.test_llm_service.LlmServiceTests.test_generate_slide_html_bundle_prompt_requires_real_asset_rendering_and_final_html -v
```

Expected: FAIL because `generate_slide_html_bundle(...)` prompt text does not yet include the stricter fixed-canvas and content-landing requirements.

### Task 2: Implement the minimal backend prompt fix

**Files:**
- Modify: `backend/app/services/llm_service.py:336-372`
- Test: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Update the batch prompt to match the single-page canvas contract**

```python
        system_prompt=(
            "你负责一次性渲染整套多页 HTML 演示稿。只返回 JSON，顶层必须包含 deck_meta 和 pages。"
            "pages 必须是逐页数组；不要返回长文档，不要把整套内容拼成一个连续页面。"
            "pages 数组中的每一页都必须是完整的 page-level HTML payload，且必须同时包含 page_id、html、css、render_meta 四个字段。"
            "每一页都必须直接返回可渲染的 html 和 css，不要返回 layout、elements、safe_area、outline、component plan 等中间设计稿字段来替代 html/css。"
            f"每一页都必须严格输出 1 张固定 {canvas_width}px × {canvas_height}px 的单页画布，比例严格为 16:9。"
            f"每一页的 html、body 和根画布容器都必须显式声明 width: {canvas_width}px; height: {canvas_height}px; margin: 0; padding: 0; overflow: hidden;。"
            "禁止使用 min-height: 100vh、height: auto、内容撑高页面、纵向堆叠无限增长、响应式长文布局。"
            "禁止 body 滚动、根容器滚动、内部容器滚动；首屏渲染时页面必须完整落入固定画布内。"
            "所有重要内容必须控制在安全区内：左右至少 80px，上方至少 64px，下方至少 56px。"
            "同一套 deck 的标题层级、正文密度、间距、引用样式必须统一。"
        )
```

- [ ] **Step 2: Update the batch prompt to require real asset rendering and final HTML output**

```python
        system_prompt=(
            ...
            "你需要直接输出最终可渲染 HTML，不要输出 placeholder、资产占位说明、Markdown 源标记或公式源码。"
            "如果 scene_specs 中存在 asset_bindings 或可复用视觉资产，应优先将其落成真实视觉结构，例如 <img>、<svg>、<table> 或其他最终 DOM。"
            "不得输出 [图表占位]、[图片占位]、placeholder、待补图片 等占位内容来替代真实视觉结构。"
            "Markdown 语法必须渲染成最终 HTML；公式必须渲染成最终可展示结构，不得直接输出 `$...$`、`$$...$$` 或未展开的 markdown 标记。"
            "除非 scene_spec 确实没有更丰富的内容，否则不要退化为 title+paragraph 式兜底布局。"
        )
```

- [ ] **Step 3: Run the focused backend tests and confirm they pass**

Run:
```bash
cd /Users/nqc233/VSCode/aiStudy/backend && python -m unittest tests.test_llm_service.LlmServiceTests.test_generate_slide_html_bundle_prompt_requires_fixed_canvas_contract tests.test_llm_service.LlmServiceTests.test_generate_slide_html_bundle_prompt_requires_real_asset_rendering_and_final_html tests.test_llm_service.LlmServiceTests.test_generate_slide_html_bundle_prompt_requires_page_level_html_css_render_meta tests.test_llm_service.LlmServiceTests.test_generate_slide_html_bundle_rejects_pages_without_html_css_shape -v
```

Expected: PASS.

### Task 3: Fix fixed-canvas rendering in the slide iframe

**Files:**
- Modify: `frontend/src/components/slides/HtmlSlideFrame.vue`
- Modify: `frontend/src/components/slides/SlidesDeckRuntime.vue`
- Test: `frontend` TypeScript build

- [ ] **Step 1: Read the existing fixed-canvas shell contract in the playback UI**

Check:
- `frontend/src/components/slides/HtmlSlideFrame.vue`
- `frontend/src/components/slides/SlidesDeckRuntime.vue`

Confirm the current issue: the iframe element is constrained to 16:9, but the inner `1600x900` document is not scaled or normalized.

- [ ] **Step 2: Implement a minimal iframe document wrapper that normalizes the inner page root**

```ts
const srcdoc = computed(() => `
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>
      html, body {
        margin: 0;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: transparent;
      }
      body {
        display: flex;
        align-items: center;
        justify-content: center;
      }
      ${props.css}
    </style>
  </head>
  <body>
    ${props.html}
  </body>
</html>
`);
```

Use it in the template:

```vue
<iframe
  class="slide-frame"
  :srcdoc="srcdoc"
  title="Rendered slide page"
/>
```

- [ ] **Step 3: Make the iframe box itself clip overflow deterministically**

```css
.slide-frame {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 0;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}
```

- [ ] **Step 4: Run the frontend type/build verification**

Run:
```bash
cd /Users/nqc233/VSCode/aiStudy/frontend && npm run build
```

Expected: PASS.

### Task 4: Run bounded regression checks and document the round

**Files:**
- Modify: `docs/checklist.md`
- Modify: `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md`

- [ ] **Step 1: Run the bounded regression commands**

Run:
```bash
cd /Users/nqc233/VSCode/aiStudy/backend && python -m unittest tests.test_llm_service -v
```

Run:
```bash
cd /Users/nqc233/VSCode/aiStudy/frontend && npm run build
```

Expected:
- The new batch prompt tests pass.
- Frontend still builds successfully.
- Do not claim unrelated pre-existing Python failures are fixed unless they are rerun and resolved.

- [ ] **Step 2: Update the factual handoff records**

Add to `docs/checklist.md` and `docs/specs/spec-15.2-slides-runtime-hardening-and-cost-control.md`:
- what changed,
- what was verified,
- remaining gap that this round may still need real-browser validation against `a38f4892-a4c5-44c6-b380-168c18a5961b`,
- confirmation that no other historical assets were rebuilt in this round.
