<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import {
  fetchAssetDetail,
  fetchAssetParseStatus,
  fetchAssetParsedDocument,
  fetchAssetPdfMeta,
  getAssetPdfUrl,
  previewAnchor,
  retryAssetParse,
  type AnchorPreviewResponse,
  type AssetDetail,
  type AssetParseStatusResponse,
  type AssetParsedDocumentResponse,
  type AssetPdfDescriptor,
  type ParsedDocumentBlock,
} from '@/api/assets';
import PdfReaderPanel from '@/components/PdfReaderPanel.vue';
import { renderMarkdownToSafeHtml } from '@/utils/markdown';
import { normalizeBlockDisplayText } from '@/utils/text';

const route = useRoute();
const assetId = computed(() => route.params.assetId as string);

const asset = ref<AssetDetail | null>(null);
const parseStatus = ref<AssetParseStatusResponse | null>(null);
const parsedDocumentResponse = ref<AssetParsedDocumentResponse | null>(null);
const pdfMeta = ref<AssetPdfDescriptor | null>(null);
const loading = ref(true);
const errorMessage = ref('');
const retrying = ref(false);
const anchorError = ref('');
const anchorPreview = ref<AnchorPreviewResponse | null>(null);
const selectedTextSnippet = ref('');
const targetPage = ref(1);
const targetBlockId = ref<string | null>(null);
let parsePollTimer: number | null = null;

const parsedDocument = computed(() => parsedDocumentResponse.value?.parsed_json ?? null);

const blockById = computed<Record<string, ParsedDocumentBlock>>(() => {
  const blocks = parsedDocument.value?.blocks ?? [];
  return Object.fromEntries(blocks.map((block) => [block.block_id, block]));
});

const currentBlock = computed(() => {
  if (!targetBlockId.value) {
    return null;
  }
  return blockById.value[targetBlockId.value] ?? null;
});

const currentPageBlocks = computed(() => {
  return (parsedDocument.value?.blocks ?? []).filter((block) => block.page_no === targetPage.value);
});

const resourceById = computed<Record<string, Record<string, unknown>>>(() => {
  const images = parsedDocument.value?.assets.images ?? [];
  const tables = parsedDocument.value?.assets.tables ?? [];
  const resources = [...images, ...tables];
  return Object.fromEntries(
    resources
      .map((resource) => [String(resource.resource_id ?? ''), resource] as const)
      .filter(([resourceId]) => resourceId),
  );
});

const tocItems = computed(() => parsedDocument.value?.toc ?? []);

const canRenderReader = computed(() => Boolean(asset.value && pdfMeta.value));

const parseTaskLabel = computed(() => parseStatus.value?.latest_parse?.task.state ?? '未开始');

const parseProgressLabel = computed(() => {
  const progress = parseStatus.value?.latest_parse?.task.progress;

  if (!progress) {
    return '等待解析结果';
  }

  if (progress.extracted_pages !== null && progress.total_pages !== null) {
    return `${progress.extracted_pages} / ${progress.total_pages} 页`;
  }

  return '正在同步进度';
});

function stopParsePolling() {
  if (parsePollTimer !== null) {
    window.clearInterval(parsePollTimer);
    parsePollTimer = null;
  }
}

function syncParsePolling() {
  stopParsePolling();

  if (!parseStatus.value || !['queued', 'processing'].includes(parseStatus.value.parse_status)) {
    return;
  }

  parsePollTimer = window.setInterval(() => {
    void loadWorkspace();
  }, 5000);
}

function focusPage(pageNo: number, blockId: string | null = null) {
  targetPage.value = pageNo;
  targetBlockId.value = blockId;
}

async function loadWorkspace() {
  loading.value = true;
  errorMessage.value = '';

  try {
    const [assetDetail, latestParseStatus, latestParsedDocument, latestPdfMeta] = await Promise.all([
      fetchAssetDetail(assetId.value),
      fetchAssetParseStatus(assetId.value),
      fetchAssetParsedDocument(assetId.value),
      fetchAssetPdfMeta(assetId.value),
    ]);

    asset.value = assetDetail;
    parseStatus.value = latestParseStatus;
    parsedDocumentResponse.value = latestParsedDocument;
    pdfMeta.value = latestPdfMeta;

    const initialPage = latestParsedDocument.parsed_json?.pages[0]?.page_no ?? 1;
    if (!targetBlockId.value) {
      targetPage.value = initialPage;
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '工作区加载失败。';
  } finally {
    loading.value = false;
    syncParsePolling();
  }
}

async function handleRetryParse() {
  retrying.value = true;
  errorMessage.value = '';

  try {
    await retryAssetParse(assetId.value);
    await loadWorkspace();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重新解析失败。';
  } finally {
    retrying.value = false;
  }
}

async function handleSelectionChange(payload: {
  pageNo: number;
  blockId: string | null;
  paragraphNo: number | null;
  selectedText: string;
}) {
  selectedTextSnippet.value = payload.selectedText;
  anchorError.value = '';
  anchorPreview.value = null;

  try {
    const response = await previewAnchor(assetId.value, {
      page_no: payload.pageNo,
      block_id: payload.blockId,
      paragraph_no: payload.paragraphNo,
      selected_text: payload.selectedText,
      selector_type: 'block',
      selector_payload: payload.blockId ? { block_id: payload.blockId } : {},
    });

    anchorPreview.value = response;
    focusPage(response.page_no, response.block_id);
  } catch (error) {
    anchorError.value = error instanceof Error ? error.message : '锚点生成失败。';
  }
}

function handlePageChange(pageNo: number) {
  targetPage.value = pageNo;
  if (targetBlockId.value && currentBlock.value?.page_no !== pageNo) {
    targetBlockId.value = null;
  }
}

function renderTocTitle(title: string): string {
  return normalizeBlockDisplayText(title) || '未命名章节';
}

function currentBlockPreviewHtml(): string {
  const block = currentBlock.value;
  if (!block) {
    return renderMarkdownToSafeHtml(null);
  }

  if (block.text) {
    return renderMarkdownToSafeHtml(block.text);
  }

  const resource = block.resource_ref ? resourceById.value[block.resource_ref] : null;
  if (!resource) {
    return renderMarkdownToSafeHtml(null);
  }

  const captions = Array.isArray(resource.caption)
    ? resource.caption.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const footnotes = Array.isArray(resource.footnote)
    ? resource.footnote.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    : [];
  const notes = [...captions, ...footnotes].join('\n\n');

  if (block.type === 'image') {
    const imageUrl = typeof resource.public_url === 'string' ? resource.public_url : '';
    if (imageUrl) {
      return renderMarkdownToSafeHtml(`![figure](${imageUrl})${notes ? `\n\n${notes}` : ''}`);
    }
  }

  if (block.type === 'table') {
    const tableHtml = typeof resource.html === 'string' ? resource.html : '';
    if (tableHtml) {
      return renderMarkdownToSafeHtml(`${tableHtml}${notes ? `\n\n${notes}` : ''}`);
    }
  }

  return renderMarkdownToSafeHtml(notes || null);
}

onMounted(() => {
  void loadWorkspace();
});

onUnmounted(() => {
  stopParsePolling();
});
</script>

<template>
  <main class="workspace-page">
    <section class="workspace-shell">
      <header class="workspace-header">
        <div>
          <p class="page-kicker">Workspace / Spec 05</p>
          <h1 v-if="asset">{{ asset.title }}</h1>
          <h1 v-else>阅读器工作区</h1>
        </div>

        <RouterLink to="/library" class="workspace-back">
          返回图书馆
        </RouterLink>
      </header>

      <section v-if="loading" class="workspace-empty">
        <h2>正在准备阅读器与定位索引...</h2>
      </section>

      <section v-else-if="errorMessage" class="workspace-empty workspace-empty--error">
        <h2>{{ errorMessage }}</h2>
      </section>

      <template v-else-if="asset">
        <section class="workspace-summary">
          <div class="workspace-summary__lead">
            <span class="summary-badge">{{ asset.source_type === 'preset' ? '预设论文' : '用户上传' }}</span>
            <span class="summary-badge summary-badge--status">{{ parseStatus?.parse_status ?? asset.basic_resources.parse_status }}</span>
          </div>

          <p class="workspace-authors">{{ asset.authors.join(' · ') }}</p>
          <p class="workspace-abstract">
            {{ asset.abstract || '当前资产还没有摘要内容，后续会由解析链路补充。' }}
          </p>
        </section>

        <section class="workspace-layout">
          <div class="workspace-layout__reader">
            <PdfReaderPanel
              v-if="canRenderReader"
              :asset-id="asset.id"
              :pdf-url="getAssetPdfUrl(asset.id)"
              :parsed-document="parsedDocument"
              :target-page="targetPage"
              :target-block-id="targetBlockId"
              @page-change="handlePageChange"
              @selection-change="handleSelectionChange"
            />
            <section v-else class="workspace-empty">
              <h2>原始 PDF 暂不可用</h2>
              <p>请先确认当前资产已经上传原始 PDF。</p>
            </section>
          </div>

          <aside class="workspace-sidebar">
            <section class="workspace-panel">
              <header class="workspace-panel__header">
                <div>
                  <p class="page-kicker">Outline</p>
                  <h2>目录导航</h2>
                </div>
                <strong>{{ tocItems.length }} 节</strong>
              </header>

              <div v-if="tocItems.length" class="toc-list">
                <button
                  v-for="item in tocItems"
                  :key="item.section_id"
                  class="toc-item"
                  type="button"
                  :style="{ '--toc-indent': String(Math.max(item.level - 1, 0)) }"
                  @click="focusPage(item.page_start)"
                >
                  <span>{{ renderTocTitle(item.title) }}</span>
                  <strong>P{{ item.page_start }}</strong>
                </button>
              </div>
              <p v-else class="workspace-muted">
                解析结果尚未生成目录结构。
              </p>
            </section>

            <section class="workspace-panel">
              <header class="workspace-panel__header">
                <div>
                  <p class="page-kicker">Locator</p>
                  <h2>当前定位</h2>
                </div>
              </header>

              <ul class="resource-list">
                <li>当前页：{{ targetPage }}</li>
                <li>当前块：{{ targetBlockId ?? '页级定位' }}</li>
                <li>段落号：{{ currentBlock?.paragraph_no ?? '-' }}</li>
                <li>页内块数：{{ currentPageBlocks.length }}</li>
              </ul>

              <article v-if="currentBlock" class="workspace-block-preview">
                <p class="page-kicker">Block Preview</p>
                <strong>{{ currentBlock.block_id }}</strong>
                <div class="workspace-block-preview__content" v-html="currentBlockPreviewHtml()" />
              </article>
            </section>

            <section class="workspace-panel">
              <header class="workspace-panel__header">
                <div>
                  <p class="page-kicker">Anchor</p>
                  <h2>锚点预览</h2>
                </div>
              </header>

              <p v-if="selectedTextSnippet" class="workspace-selection-snippet">
                {{ selectedTextSnippet }}
              </p>
              <p v-else class="workspace-muted">
                在左侧当前页文本块中选中文本后，这里会生成统一锚点对象。
              </p>

              <p v-if="anchorError" class="workspace-parse-error">
                {{ anchorError }}
              </p>

              <pre v-if="anchorPreview" class="workspace-json-preview">{{ JSON.stringify(anchorPreview, null, 2) }}</pre>
            </section>

            <section class="workspace-panel">
              <header class="workspace-panel__header">
                <div>
                  <p class="page-kicker">Pipeline</p>
                  <h2>解析状态</h2>
                </div>
              </header>

              <ul class="resource-list">
                <li>资产状态：{{ asset.status }}</li>
                <li>解析状态：{{ parseStatus?.parse_status ?? asset.basic_resources.parse_status }}</li>
                <li>MinerU 状态：{{ parseTaskLabel }}</li>
                <li>解析进度：{{ parseProgressLabel }}</li>
                <li>parsed_json：{{ parsedDocument ? '已就绪' : '未就绪' }}</li>
              </ul>

              <div class="workspace-actions">
                <button class="toolbar-button toolbar-button--ghost" type="button" @click="loadWorkspace">
                  刷新工作区
                </button>
                <button
                  v-if="parseStatus?.parse_status === 'failed'"
                  class="toolbar-button"
                  type="button"
                  :disabled="retrying"
                  @click="handleRetryParse"
                >
                  {{ retrying ? '重新排队中...' : '重新解析' }}
                </button>
              </div>
            </section>
          </aside>
        </section>
      </template>
    </section>
  </main>
</template>
