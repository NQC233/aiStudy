import { expect, test, type Page, type Route } from '@playwright/test';

type FlowMode =
  | 'auto-resume'
  | 'next-failed'
  | 'current-retrying'
  | 'schema-rebuilding'
  | 'schema-rebuilding-then-ready'
  | 'diagram-svg'
  | 'flow-comparison';

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
  return {
    asset_id: 'asset-e2e',
    schema_version: '2',
    rebuilding: false,
    rebuild_reason: null,
    slides_status: 'ready',
    tts_status: 'processing',
    playback_status: 'ready',
    auto_page_supported: true,
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

async function mockSlidesApi(page: Page, mode: FlowMode) {
  const state = {
    slides: buildSlidesSnapshot(),
    ensureNextCalls: 0,
    slidesFetchCalls: 0,
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

  if (mode === 'schema-rebuilding') {
    state.slides.slides_status = 'processing';
    state.slides.rebuilding = true;
    state.slides.rebuild_reason = 'schema_upgrade_rebuild';
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
      state.slides.rebuilding = false;
      state.slides.rebuild_reason = null;
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
}

test('auto page waits then resumes when next tts becomes ready', async ({ page }) => {
  await mockSlidesApi(page, 'auto-resume');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');
  await expect(page.getByRole('heading', { name: 'Spec12 E2E Asset' })).toBeVisible();

  await page.getByRole('button', { name: '播放' }).click();
  await expect(page.locator('.slides-stage__counter')).toHaveText('2 / 2', { timeout: 10000 });
  await expect(page.getByRole('heading', { name: /方法概览/ })).toBeVisible();
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

test('shows auto rebuilding hint when legacy slides are upgrading', async ({ page }) => {
  await mockSlidesApi(page, 'schema-rebuilding');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.getByText('检测到旧版演示结构，系统正在自动升级重建，请稍后自动刷新。')).toBeVisible();
});

test('auto refreshes and recovers when schema rebuilding completes', async ({ page }) => {
  await mockSlidesApi(page, 'schema-rebuilding-then-ready');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.getByRole('heading', { name: /问题背景/ })).toBeVisible({ timeout: 10000 });
});

test('renders diagram svg block with script stripped', async ({ page }) => {
  await mockSlidesApi(page, 'diagram-svg');

  page.on('dialog', async (dialog) => {
    throw new Error(`unexpected dialog: ${dialog.message()}`);
  });

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');
  await expect(page.locator('.slides-diagram svg')).toBeVisible();
  await expect(page.locator('.slides-diagram script')).toHaveCount(0);
});

test('renders specialized comparison and flow blocks', async ({ page }) => {
  await mockSlidesApi(page, 'flow-comparison');

  await page.goto('/workspace/asset-e2e/slides?runtime=legacy');

  await expect(page.locator('.slides-comparison')).toBeVisible();
  await expect(page.locator('.slides-flow')).toBeVisible();
  await expect(page.getByText('方案')).toBeVisible();
  await expect(page.getByText('本方法')).toBeVisible();
  await expect(page.getByText('门控融合')).toBeVisible();
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

test('uses reveal runtime by default for slides route', async ({ page }) => {
  await mockSlidesApi(page, 'auto-resume');

  await page.goto('/workspace/asset-e2e/slides');

  await expect(page.locator('.reveal-stage .reveal')).toBeVisible();
});
