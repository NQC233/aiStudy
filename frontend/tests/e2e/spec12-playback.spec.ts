import { expect, test, type Page, type Route } from '@playwright/test';

type FlowMode =
  | 'auto-resume'
  | 'next-failed'
  | 'current-retrying'
  | 'schema-rebuilding'
  | 'schema-rebuilding-then-ready'
  | 'diagram-svg'
  | 'flow-comparison'
  | 'reveal-layout'
  | 'playback-not-ready'
  | 'partial-ready'
  | 'fullscreen';

function buildAssetDetail(assetId: string) {
  const now = new Date().toISOString();
  return {
    id: assetId,
    user_id: 'user-e2e',
    title: 'Spec12 E2E Asset',
    authors: ['Tester'],
    abstract: null,
    source_type: 'upload',
    language: 'zh',
    status: 'ready',
    parse_error_message: null,
    created_at: now,
    updated_at: now,
    basic_resources: {
      parse_status: 'ready',
      kb_status: 'ready',
      mindmap_status: 'ready',
    },
    enhanced_resources: {
      slides_status: 'ready',
      anki_status: 'not_generated',
      quiz_status: 'not_generated',
    },
  };
}

function buildSlidesSnapshot() {
  const runtimePages = [
    {
      page_id: 'slide:problem:1',
      html: '<section><h1>问题背景</h1><p>明确问题边界</p></section>',
      css: '.page{}',
      asset_refs: [],
      render_meta: { layout_strategy: 'hero-left' },
    },
    {
      page_id: 'slide:method:2',
      html: '<section><h1>方法概览</h1><p>理解方法流程</p></section>',
      css: '.page{}',
      asset_refs: [],
      render_meta: { layout_strategy: 'insight-stack' },
    },
  ];

  return {
    asset_id: 'asset-e2e',
    schema_version: '2',
    rebuilding: false,
    rebuild_reason: null,
    slides_status: 'ready',
    tts_status: 'processing',
    playback_status: 'ready',
    auto_page_supported: true,
    runtime_bundle: {
      page_count: runtimePages.length,
      pages: runtimePages,
      playable_page_count: runtimePages.length,
      failed_page_numbers: [],
      validation_summary: {
        status: 'ready',
        reason: null,
      },
    },
    slides_dsl: {
      schema_version: '2',
      asset_id: 'asset-e2e',
      version: 1,
      generated_at: new Date().toISOString(),
      pages: [
        {
          slide_key: 'slide:problem:1',
          stage: 'problem',
          page_type: 'topic',
          layout_hint: 'hero-left',
          director_source: 'rule',
          template_type: 'topic_deep_dive',
          animation_preset: 'stagger_reveal',
          animations: [],
          blocks: [
            { block_type: 'title', content: '问题背景', items: [] },
            { block_type: 'key_points', content: '', items: ['明确问题边界', '解释主要挑战'] },
            { block_type: 'evidence', content: '', items: ['引用关键证据'] },
            { block_type: 'speaker_note', content: '第一页讲稿。', items: [] },
          ],
          citations: [],
        },
        {
          slide_key: 'slide:method:2',
          stage: 'method',
          page_type: 'topic',
          layout_hint: 'insight-stack',
          director_source: 'rule',
          template_type: 'topic_deep_dive',
          animation_preset: 'stagger_reveal',
          animations: [],
          blocks: [
            { block_type: 'title', content: '方法概览', items: [] },
            { block_type: 'key_points', content: '', items: ['理解方法流程', '关注核心模块'] },
            { block_type: 'evidence', content: '', items: ['对照实验结果'] },
            { block_type: 'speaker_note', content: '第二页讲稿。', items: [] },
          ],
          citations: [],
        },
      ],
    },
    must_pass_report: null,
    quality_report: { overall_score: 0.92, details: [] },
    fix_logs: [],
    generation_meta: {
      requested_strategy: 'template',
      applied_strategy: 'template',
      fallback_used: false,
      fallback_reason: null,
    },
    shadow_report: {
      status: 'not_run',
      baseline_strategy: 'template',
      candidate_strategy: 'llm',
      baseline_score: null,
      candidate_score: null,
      score_delta: null,
      skip_reason: 'disabled',
    },
    tts_manifest: {
      pages: [
        {
          slide_key: 'slide:problem:1',
          audio_url: 'https://example.com/audio/page-1.mp3',
          duration_ms: 1600,
          status: 'ready',
          error_message: null,
        },
        {
          slide_key: 'slide:method:2',
          audio_url: null,
          duration_ms: 1600,
          status: 'pending',
          error_message: null,
        },
      ],
    },
    playback_plan: {
      total_duration_ms: 3200,
      pages: [
        {
          slide_key: 'slide:problem:1',
          start_ms: 0,
          end_ms: 1600,
          duration_ms: 1600,
          cues: [
            { block_id: 'slide:problem:1:goal:1', start_ms: 200, end_ms: 800, animation: 'title_in' },
            { block_id: 'slide:problem:1:evidence:1', start_ms: 800, end_ms: 1500, animation: 'title_in' },
          ],
        },
        {
          slide_key: 'slide:method:2',
          start_ms: 1600,
          end_ms: 3200,
          duration_ms: 1600,
          cues: [
            { block_id: 'slide:method:2:goal:1', start_ms: 200, end_ms: 800, animation: 'bullet_stagger' },
            { block_id: 'slide:method:2:evidence:1', start_ms: 800, end_ms: 1500, animation: 'bullet_stagger' },
          ],
        },
      ],
    },
  };
}

async function mockWorkspaceSupportApi(page: Page) {
  const now = new Date().toISOString();
  await page.route('**/api/assets/asset-e2e/status', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        asset_status: 'ready',
        parse_status: 'ready',
        error_message: null,
        latest_parse: {
          id: 'parse-1',
          asset_id: 'asset-e2e',
          provider: 'mineru',
          parse_version: 'v1',
          status: 'succeeded',
          markdown_storage_key: null,
          json_storage_key: null,
          raw_response_storage_key: null,
          error_code: null,
          retryable: null,
          attempt: null,
          max_retries: null,
          next_retry_eta: null,
          task: {
            task_id: null,
            data_id: null,
            state: null,
            trace_id: null,
            full_zip_url: null,
            err_msg: null,
            progress: null,
          },
          created_at: now,
          updated_at: now,
        },
      }),
    });
  });
  await page.route('**/api/assets/asset-e2e/parsed-json', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        parse_status: 'ready',
        parse_id: 'parse-1',
        parsed_json: {
          schema_version: '1.0',
          asset_id: 'asset-e2e',
          parse_id: 'parse-1',
          provider: {},
          document: {},
          pages: [{ page_id: 'p1', page_no: 1, source_page_idx: 0, width: null, height: null, blocks: [] }],
          sections: [],
          blocks: [],
          assets: { images: [], tables: [] },
          reading_order: [],
          toc: [],
          stats: {},
        },
      }),
    });
  });
  await page.route('**/api/assets/asset-e2e/pdf-meta', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        file_id: 'file-1',
        file_type: 'pdf',
        mime_type: 'application/pdf',
        size: 1024,
        url: 'http://example.com/a.pdf',
      }),
    });
  });
  await page.route('**/api/assets/asset-e2e/mindmap', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ asset_id: 'asset-e2e', mindmap_status: 'ready', mindmap: null }),
    });
  });
  await page.route('**/api/assets/asset-e2e/chat/sessions', async (route: Route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route(/.*\/api\/assets\/asset-e2e\/notes(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ asset_id: 'asset-e2e', total: 0, anchor_type: null, notes: [] }),
    });
  });
}

async function mockSlidesApi(page: Page, mode: FlowMode) {
  const state = {
    slides: buildSlidesSnapshot(),
    ensureNextCalls: 0,
    slidesFetchCalls: 0,
    rebuildRequests: [] as Array<Record<string, unknown>>,
  };

  if (mode === 'current-retrying') {
    state.slides.tts_manifest.pages[0].status = 'processing';
    state.slides.tts_manifest.pages[0].retry_meta = {
      attempt: 2,
      max_retries: 5,
      auto_retry_pending: true,
      next_retry_eta: '2026-04-07T12:00:00Z',
      error_code: 'external_dependency',
    };
  }

  if (mode === 'schema-rebuilding' || mode === 'schema-rebuilding-then-ready') {
    state.slides.slides_status = 'processing';
    state.slides.playback_status = 'not_ready';
    state.slides.auto_page_supported = false;
    state.slides.rebuilding = true;
    state.slides.rebuild_reason = 'schema_upgrade_rebuild';
    state.slides.runtime_bundle = {
      page_count: 0,
      pages: [],
      playable_page_count: 0,
      failed_page_numbers: [],
      validation_summary: {
        status: 'not_ready',
        reason: 'schema_upgrade_rebuild',
      },
    };
    state.slides.slides_dsl = null;
  }

  if (mode === 'diagram-svg') {
    state.slides.slides_dsl.pages[0].page_type = 'diagram';
    state.slides.slides_dsl.pages[0].blocks.push({
      block_type: 'diagram_svg',
      content: '',
      items: [],
      svg_content:
        "<svg viewBox='0 0 100 40' xmlns='http://www.w3.org/2000/svg'><rect x='1' y='1' width='98' height='38' fill='#eee'/><text x='10' y='24'>diagram</text><script>alert('x')</script></svg>",
    });
    state.slides.runtime_bundle.pages[0].html = [
      '<section>',
      '  <div class="slides-diagram">',
      "    <svg viewBox='0 0 100 40' xmlns='http://www.w3.org/2000/svg'><rect x='1' y='1' width='98' height='38' fill='#eee'/><text x='10' y='24'>diagram</text></svg>",
      '  </div>',
      '</section>',
    ].join('');
  }

  if (mode === 'flow-comparison') {
    state.slides.slides_dsl.pages[0].blocks = [
      { block_type: 'title', content: '方法对比', items: [] },
      {
        block_type: 'comparison',
        content: '',
        items: [],
        meta: {
          columns: ['方案', '精度', '时延'],
          rows: [
            ['基线方法', '88%', '120ms'],
            ['本方法', '91%', '95ms'],
          ],
        },
      },
      {
        block_type: 'flow',
        content: '',
        items: [],
        meta: {
          steps: ['输入预处理', '双路编码', '门控融合', '结果输出'],
        },
      },
      { block_type: 'speaker_note', content: '先对比指标，再解释流程。', items: [] },
    ];
    state.slides.runtime_bundle.pages[0].html = [
      '<section>',
      '  <h1>方法对比</h1>',
      '  <div class="slides-comparison">',
      '    <span>方案</span>',
      '    <span>本方法</span>',
      '  </div>',
      '  <div class="slides-flow">',
      '    <span>门控融合</span>',
      '  </div>',
      '</section>',
    ].join('');
  }

  if (mode === 'reveal-layout') {
    state.slides.slides_dsl.pages[0].layout_hint = 'split-evidence';
    state.slides.runtime_bundle.pages[0].html = [
      '<section class="runtime-layout runtime-layout--split-evidence">',
      '  <h1>问题背景</h1>',
      '  <p>双栏证据布局</p>',
      '</section>',
    ].join('');
  }


  if (mode === 'partial-ready') {
    state.slides.playback_status = 'partial_ready';
    state.slides.auto_page_supported = true;
    state.slides.failed_page_numbers = [2];
    if (state.slides.runtime_bundle) {
      state.slides.runtime_bundle.failed_page_numbers = [2];
      state.slides.runtime_bundle.playable_page_count = 1;
      state.slides.runtime_bundle.validation_summary = {
        status: 'partial_ready',
        reason: 'overflow_detected',
      };
      state.slides.runtime_bundle.pages[1].render_meta = {
        layout_strategy: 'insight-stack',
        validation: {
          status: 'failed',
          blocking: true,
          reason: 'overflow_detected',
        },
        runtime_gate_status: 'failed',
      };
    }
  }

  if (mode === 'fullscreen') {
    await page.addInitScript(() => {
      const requestFullscreenMock = async function requestFullscreenMock(this: HTMLElement) {
        Object.defineProperty(document, 'fullscreenElement', {
          configurable: true,
          get: () => this,
        });
        document.dispatchEvent(new Event('fullscreenchange'));
      };

      const exitFullscreenMock = async function exitFullscreenMock() {
        Object.defineProperty(document, 'fullscreenElement', {
          configurable: true,
          get: () => null,
        });
        document.dispatchEvent(new Event('fullscreenchange'));
      };

      Object.defineProperty(document, 'fullscreenElement', {
        configurable: true,
        get: () => null,
      });
      Object.defineProperty(HTMLElement.prototype, 'requestFullscreen', {
        configurable: true,
        writable: true,
        value: requestFullscreenMock,
      });
      Object.defineProperty(document, 'exitFullscreen', {
        configurable: true,
        writable: true,
        value: exitFullscreenMock,
      });
    });
  }

  await page.addInitScript(() => {
    const playMock = function playMock(this: HTMLMediaElement) {
      window.setTimeout(() => {
        this.dispatchEvent(new Event('timeupdate'));
      }, 10);
      window.setTimeout(() => {
        this.dispatchEvent(new Event('ended'));
      }, 80);
      return Promise.resolve();
    };

    const pauseMock = function pauseMock() {
      return undefined;
    };

    const loadMock = function loadMock(this: HTMLMediaElement) {
      window.setTimeout(() => {
        this.dispatchEvent(new Event('loadedmetadata'));
      }, 0);
      return undefined;
    };

    Object.defineProperty(HTMLMediaElement.prototype, 'play', {
      configurable: true,
      writable: true,
      value: playMock,
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'pause', {
      configurable: true,
      writable: true,
      value: pauseMock,
    });
    Object.defineProperty(HTMLMediaElement.prototype, 'load', {
      configurable: true,
      writable: true,
      value: loadMock,
    });
  });

  await page.route('**/api/assets/asset-e2e', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildAssetDetail('asset-e2e')),
    });
  });

  await page.route('**/api/assets/asset-e2e/slides', async (route: Route) => {
    state.slidesFetchCalls += 1;
    if (mode === 'schema-rebuilding-then-ready' && state.slidesFetchCalls >= 4) {
      state.slides.slides_status = 'ready';
      state.slides.playback_status = 'ready';
      state.slides.auto_page_supported = true;
      state.slides.rebuilding = false;
      state.slides.rebuild_reason = null;
      state.slides.runtime_bundle = buildSlidesSnapshot().runtime_bundle;
      state.slides.slides_dsl = buildSlidesSnapshot().slides_dsl;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(state.slides),
    });
  });

  await page.route('**/api/assets/asset-e2e/slides/tts/ensure', async (route: Route) => {
    const body = route.request().postDataJSON() as { page_index: number; prefetch_next?: boolean };

    if (body.page_index === 1) {
      state.ensureNextCalls += 1;
      const nextPage = state.slides.tts_manifest.pages[1];
      if (mode === 'auto-resume') {
        if (state.ensureNextCalls >= 2) {
          nextPage.status = 'ready';
          nextPage.audio_url = 'https://example.com/audio/page-2.mp3';
          nextPage.error_message = null;
          state.slides.tts_status = 'ready';
        } else {
          nextPage.status = 'processing';
          nextPage.audio_url = null;
          state.slides.tts_status = 'processing';
        }
      } else {
        nextPage.status = 'failed';
        nextPage.audio_url = null;
        nextPage.error_message = 'tts provider error';
        state.slides.tts_status = 'partial';
      }
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        page_index: body.page_index,
        enqueued_slide_keys: body.page_index === 1 ? ['slide:method:2'] : [],
        tts_status: state.slides.tts_status,
        message: 'ok',
      }),
    });
  });

  await page.route('**/api/assets/asset-e2e/slides/tts/retry-next', async (route: Route) => {
    const nextPage = state.slides.tts_manifest.pages[1];
    nextPage.status = 'ready';
    nextPage.audio_url = 'https://example.com/audio/page-2.mp3';
    nextPage.error_message = null;
    state.slides.tts_status = 'ready';

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        current_page_index: 0,
        next_slide_key: 'slide:method:2',
        enqueued_slide_keys: ['slide:method:2'],
        tts_status: 'processing',
        message: '下一页已重新加入 TTS 生成队列。',
      }),
    });
  });

  await page.route('**/api/assets/asset-e2e/slides/runtime-bundle/rebuild', async (route: Route) => {
    const payload = route.request().postDataJSON() as {
      from_stage?: 'full' | 'scene' | 'html' | 'runtime';
      page_numbers?: number[];
      failed_only?: boolean;
    };
    state.rebuildRequests.push(payload);

    if (payload.from_stage === 'html' && Array.isArray(payload.page_numbers) && payload.page_numbers.length > 0) {
      for (const pageNumber of payload.page_numbers) {
        const pageIndex = pageNumber - 1;
        if (state.slides.runtime_bundle?.pages?.[pageIndex]) {
          state.slides.runtime_bundle.pages[pageIndex].html = `<section><h1>updated-page-${pageNumber}</h1></section>`;
        }
      }
    }

    if (payload.from_stage === 'html' && payload.failed_only) {
      for (const failedPageNumber of state.slides.failed_page_numbers ?? []) {
        const pageIndex = failedPageNumber - 1;
        if (state.slides.runtime_bundle?.pages?.[pageIndex]) {
          state.slides.runtime_bundle.pages[pageIndex].html = `<section><h1>updated-failed-${failedPageNumber}</h1></section>`;
        }
      }
      state.slides.failed_page_numbers = [];
      if (state.slides.runtime_bundle) {
        state.slides.runtime_bundle.failed_page_numbers = [];
        state.slides.runtime_bundle.playable_page_count = state.slides.runtime_bundle.page_count;
        state.slides.runtime_bundle.validation_summary = {
          status: 'ready',
          reason: null,
        };
      }
      state.slides.playback_status = 'ready';
      state.slides.auto_page_supported = true;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        slides_status: state.slides.slides_status,
        schema_version: state.slides.schema_version,
        playback_status: state.slides.playback_status,
        playable_page_count: state.slides.runtime_bundle?.playable_page_count ?? 0,
        failed_page_numbers: state.slides.failed_page_numbers,
        rebuild_meta: {
          from_stage: payload.from_stage ?? 'html',
          requested_page_numbers: payload.page_numbers ?? [],
          effective_page_numbers: payload.page_numbers ?? (payload.failed_only ? [2] : []),
          failed_only: Boolean(payload.failed_only),
          reused_layers: ['scene_specs'],
          rebuilt_layers: ['rendered_slide_pages', 'runtime_bundle'],
        },
        runtime_bundle: state.slides.runtime_bundle,
      }),
    });
  });

  return state;
}

test('auto page waits then resumes when next tts becomes ready', async ({ page }) => {
  await mockSlidesApi(page, 'auto-resume');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');
  await expect(page.getByRole('heading', { name: 'Spec12 E2E Asset' })).toBeVisible();

  await page.getByRole('button', { name: '播放' }).click();
  await expect(page.locator('.slides-stage__counter')).toHaveText('2 / 2', { timeout: 10000 });
  await expect(page.frameLocator('.slide-frame').getByRole('heading', { name: /方法概览/ })).toBeVisible();
});

test('shows retry-next action when next page generation fails', async ({ page }) => {
  await mockSlidesApi(page, 'next-failed');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');
  await page.getByRole('button', { name: '播放' }).click();

  await expect(page.getByRole('button', { name: '重试下一页' })).toBeVisible({ timeout: 10000 });
  await page.getByRole('button', { name: '重试下一页' }).click();

  await expect(page.getByText('下一页已重新加入 TTS 生成队列。')).toBeVisible();
});

test('shows retrying hint when current page tts is auto retrying', async ({ page }) => {
  await mockSlidesApi(page, 'current-retrying');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.getByText('自动重试中（2/5）')).toBeVisible();
});

test('allows workspace entry and playback render for partial_ready slides', async ({ page }) => {
  await mockSlidesApi(page, 'partial-ready');
  await mockWorkspaceSupportApi(page);

  await page.goto('/workspace/asset-e2e');
  await expect(page.getByRole('button', { name: '进入演示播放页' })).toBeEnabled();
  await expect(page.getByText('Playback: partial_ready')).toBeVisible();

  await page.goto('/workspace/asset-e2e/slides');
  await expect(page.frameLocator('.slide-frame').getByRole('heading', { name: /问题背景/ })).toBeVisible();
  await expect(page.getByText('失败页：2')).toBeVisible();
  await expect(page.getByRole('button', { name: '仅重建失败页' })).toBeVisible();
});

test('blocks pseudo-ready playback from workspace and play page', async ({ page }) => {
  await mockSlidesApi(page, 'playback-not-ready');
  await mockWorkspaceSupportApi(page);

  await page.goto('/workspace/asset-e2e');
  await expect(page.getByRole('button', { name: '演示内容未就绪' })).toBeDisabled();

  await page.goto('/workspace/asset-e2e/slides');
  await expect(page.getByText('当前演示内容尚未就绪，请返回工作区重建或重试。')).toBeVisible();
  await expect(page.locator('.slides-stage__counter')).toHaveCount(0);
});

test('shows auto rebuilding hint when legacy slides are upgrading', async ({ page }) => {
  await mockSlidesApi(page, 'schema-rebuilding');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.getByText('检测到旧版演示结构，系统正在自动升级重建，请稍后自动刷新。')).toBeVisible();
});

test('auto refreshes and recovers when schema rebuilding completes', async ({ page }) => {
  await mockSlidesApi(page, 'schema-rebuilding-then-ready');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.frameLocator('.slide-frame').getByRole('heading', { name: /问题背景/ })).toBeVisible({ timeout: 10000 });
});

test('renders diagram svg block with script stripped', async ({ page }) => {
  await mockSlidesApi(page, 'diagram-svg');

  page.on('dialog', async (dialog) => {
    throw new Error(`unexpected dialog: ${dialog.message()}`);
  });

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');
  await expect(page.frameLocator('.slide-frame').locator('.slides-diagram svg')).toBeVisible();
  await expect(page.frameLocator('.slide-frame').locator('.slides-diagram script')).toHaveCount(0);
});

test('renders specialized comparison and flow blocks', async ({ page }) => {
  await mockSlidesApi(page, 'flow-comparison');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.frameLocator('.slide-frame').locator('.slides-comparison')).toBeVisible();
  await expect(page.frameLocator('.slide-frame').locator('.slides-flow')).toBeVisible();
  await expect(page.frameLocator('.slide-frame').getByText('方案')).toBeVisible();
  await expect(page.frameLocator('.slide-frame').getByText('本方法')).toBeVisible();
  await expect(page.frameLocator('.slide-frame').getByText('门控融合')).toBeVisible();
});

test('shows slides retry summary on workspace status card', async ({ page }) => {
  const now = new Date().toISOString();
  await page.route('**/api/assets/asset-e2e', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildAssetDetail('asset-e2e')),
    });
  });
  await page.route('**/api/assets/asset-e2e/status', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        asset_status: 'ready',
        parse_status: 'ready',
        error_message: null,
        latest_parse: {
          id: 'parse-1',
          asset_id: 'asset-e2e',
          provider: 'mineru',
          parse_version: 'v1',
          status: 'succeeded',
          markdown_storage_key: null,
          json_storage_key: null,
          raw_response_storage_key: null,
          error_code: null,
          retryable: null,
          attempt: null,
          max_retries: null,
          next_retry_eta: null,
          task: {
            task_id: null,
            data_id: null,
            state: null,
            trace_id: null,
            full_zip_url: null,
            err_msg: null,
            progress: null,
          },
          created_at: now,
          updated_at: now,
        },
      }),
    });
  });
  await page.route('**/api/assets/asset-e2e/parsed-json', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        parse_status: 'ready',
        parse_id: 'parse-1',
        parsed_json: {
          schema_version: '1.0',
          asset_id: 'asset-e2e',
          parse_id: 'parse-1',
          provider: {},
          document: {},
          pages: [{ page_id: 'p1', page_no: 1, source_page_idx: 0, width: null, height: null, blocks: [] }],
          sections: [],
          blocks: [],
          assets: { images: [], tables: [] },
          reading_order: [],
          toc: [],
          stats: {},
        },
      }),
    });
  });
  await page.route('**/api/assets/asset-e2e/pdf-meta', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        asset_id: 'asset-e2e',
        file_id: 'file-1',
        file_type: 'pdf',
        mime_type: 'application/pdf',
        size: 1024,
        url: 'http://example.com/a.pdf',
      }),
    });
  });
  await page.route('**/api/assets/asset-e2e/mindmap', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ asset_id: 'asset-e2e', mindmap_status: 'ready', mindmap: null }),
    });
  });
  await page.route('**/api/assets/asset-e2e/chat/sessions', async (route: Route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) });
  });
  await page.route(/.*\/api\/assets\/asset-e2e\/notes(\?.*)?$/, async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ asset_id: 'asset-e2e', total: 0, anchor_type: null, notes: [] }),
    });
  });
  await page.route('**/api/assets/asset-e2e/slides', async (route: Route) => {
    const slides = buildSlidesSnapshot();
    slides.tts_manifest.pages[0].status = 'processing';
    slides.tts_manifest.pages[0].retry_meta = {
      attempt: 2,
      max_retries: 5,
      auto_retry_pending: true,
      next_retry_eta: '2026-04-07T12:00:00Z',
      error_code: 'external_dependency',
    };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(slides) });
  });

  await page.goto('/workspace/asset-e2e');
  await expect(page.getByText('Slides 重试中（2/5）').first()).toBeVisible();
});

test('toggles fullscreen within html runtime deck', async ({ page }) => {
  await mockSlidesApi(page, 'fullscreen');

  await page.goto('/workspace/asset-e2e/slides');

  const fullscreenButton = page.getByRole('button', { name: '进入全屏' });
  await expect(fullscreenButton).toBeVisible();

  await fullscreenButton.click();
  await expect(page.locator('.slides-deck-runtime__viewport--fullscreen')).toBeVisible();
  await expect(page.getByRole('button', { name: '退出全屏' })).toBeVisible();
  await expect(page.frameLocator('.slide-frame').getByRole('heading', { name: /问题背景/ })).toBeVisible();

  await page.getByRole('button', { name: '退出全屏' }).click();
  await expect(page.locator('.slides-deck-runtime__viewport--fullscreen')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '进入全屏' })).toBeVisible();
});

test('renders custom runtime layout markup from page html', async ({ page }) => {
  await mockSlidesApi(page, 'reveal-layout');

  await page.goto('/workspace/asset-e2e/slides');

  await expect(page.frameLocator('.slide-frame').locator('.runtime-layout--split-evidence')).toBeVisible();
});

test('submits page-scoped html rebuild from playback page', async ({ page }) => {
  const state = await mockSlidesApi(page, 'fullscreen');

  await page.goto('/workspace/asset-e2e/slides');

  await page.getByRole('combobox').selectOption('2');
  await page.getByRole('button', { name: '重建所选页 HTML' }).click();

  await expect(page.getByText('已提交第 2 页 HTML 重建，正在刷新演示状态。')).toBeVisible();
  await expect(page.getByText('失败页：无')).toBeVisible();
  await expect.poll(() => state.rebuildRequests.length).toBe(1);
  await expect.poll(() => state.rebuildRequests[0]).toEqual({
    from_stage: 'html',
    page_numbers: [2],
  });
});

test('submits failed-only html rebuild from playback page', async ({ page }) => {
  const state = await mockSlidesApi(page, 'fullscreen');
  state.slides.playback_status = 'not_ready';
  state.slides.auto_page_supported = false;
  state.slides.failed_page_numbers = [2];
  if (state.slides.runtime_bundle) {
    state.slides.runtime_bundle.failed_page_numbers = [2];
    state.slides.runtime_bundle.playable_page_count = 1;
    state.slides.runtime_bundle.validation_summary = {
      status: 'not_ready',
      reason: 'overflow_detected',
    };
    state.slides.runtime_bundle.pages[1].render_meta = {
      layout_strategy: 'insight-stack',
      validation: {
        status: 'failed',
        blocking: true,
        reason: 'overflow_detected',
      },
      runtime_gate_status: 'failed',
    };
  }

  await page.goto('/workspace/asset-e2e/slides');

  await page.getByRole('button', { name: '仅重建失败页' }).click();

  await expect(page.getByText('已提交失败页 HTML 重建，正在刷新演示状态。')).toBeVisible();
  await expect(page.getByText('失败页：无')).toBeVisible();
  await expect.poll(() => state.rebuildRequests.length).toBe(1);
  await expect.poll(() => state.rebuildRequests[0]).toEqual({
    from_stage: 'html',
    failed_only: true,
  });
});
