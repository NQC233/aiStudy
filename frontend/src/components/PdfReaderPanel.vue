<script setup lang="ts">
import { computed, markRaw, nextTick, onMounted, ref, shallowRef, watch } from 'vue';
import { GlobalWorkerOptions, getDocument, TextLayer } from 'pdfjs-dist';
import pdfjsWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'katex/dist/katex.min.css';

import type { ParsedDocumentBlock, ParsedDocumentPayload } from '@/api/assets';
import { renderMarkdownToSafeHtml } from '@/utils/markdown';
import { normalizeBlockDisplayText } from '@/utils/text';

interface ReaderSelectionPayload {
  pageNo: number;
  blockId: string | null;
  paragraphNo: number | null;
  selectedText: string;
}

const props = defineProps<{
  assetId: string;
  pdfUrl: string;
  parsedDocument: ParsedDocumentPayload | null;
  targetPage: number;
  targetBlockId: string | null;
}>();

const emit = defineEmits<{
  'page-change': [pageNo: number];
  'selection-change': [payload: ReaderSelectionPayload];
}>();

GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

const canvasRef = ref<HTMLCanvasElement | null>(null);
const textLayerRef = ref<HTMLElement | null>(null);
const blockTextLayerRef = ref<HTMLElement | null>(null);
const currentPage = ref(1);
const totalPages = ref(1);
const scale = ref(1.15);
const pdfDocument = shallowRef<any>(null);
const loading = ref(true);
const renderError = ref('');
const usingFallbackPreview = ref(false);
const rendering = ref(false);
let pdfInitTimeoutId: number | null = null;
let currentTextLayerRenderId = 0;

const blockById = computed<Record<string, ParsedDocumentBlock>>(() => {
  const entries = props.parsedDocument?.blocks ?? [];
  return Object.fromEntries(entries.map((block) => [block.block_id, block]));
});

const currentPageBlocks = computed(() => {
  return (props.parsedDocument?.blocks ?? []).filter((block) => block.page_no === currentPage.value);
});

const resourceById = computed<Record<string, Record<string, unknown>>>(() => {
  const images = props.parsedDocument?.assets.images ?? [];
  const tables = props.parsedDocument?.assets.tables ?? [];
  const resources = [...images, ...tables];
  return Object.fromEntries(
    resources
      .map((resource) => [String(resource.resource_id ?? ''), resource] as const)
      .filter(([resourceId]) => resourceId),
  );
});

const selectedBlockContext = computed(() => {
  if (!props.targetBlockId) {
    return null;
  }
  return blockById.value[props.targetBlockId] ?? null;
});

function renderBlockHtml(block: ParsedDocumentBlock): string {
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
      const markdown = `![figure](${imageUrl})${notes ? `\n\n${notes}` : ''}`;
      return renderMarkdownToSafeHtml(markdown);
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

async function renderPage(pageNo: number) {
  if (!pdfDocument.value || !canvasRef.value || rendering.value) {
    return;
  }

  rendering.value = true;
  renderError.value = '';
  const renderId = ++currentTextLayerRenderId;

  try {
    const page = await pdfDocument.value.getPage(pageNo);
    const viewport = page.getViewport({ scale: scale.value });
    const canvas = canvasRef.value;
    const context = canvas.getContext('2d');
    const outputScale = window.devicePixelRatio || 1;

    if (!context) {
      throw new Error('无法初始化 PDF 画布。');
    }

    canvas.width = Math.ceil(viewport.width * outputScale);
    canvas.height = Math.ceil(viewport.height * outputScale);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;

    if (textLayerRef.value) {
      textLayerRef.value.innerHTML = '';
      textLayerRef.value.style.width = `${viewport.width}px`;
      textLayerRef.value.style.height = `${viewport.height}px`;
    }

    await page.render({
      canvasContext: context,
      viewport,
      transform: outputScale === 1 ? undefined : [outputScale, 0, 0, outputScale, 0, 0],
    }).promise;

    if (renderId === currentTextLayerRenderId && textLayerRef.value) {
      const textContent = await page.getTextContent();
      const textLayer = new TextLayer({
        textContentSource: textContent,
        container: textLayerRef.value,
        viewport,
      });
      await textLayer.render();
    }

    emit('page-change', pageNo);
  } catch (error) {
    renderError.value = error instanceof Error ? error.message : 'PDF 页面渲染失败。';
  } finally {
    rendering.value = false;
    loading.value = false;
  }
}

async function openDocument() {
  loading.value = true;
  renderError.value = '';
  usingFallbackPreview.value = false;
  await nextTick();

  if (pdfInitTimeoutId !== null) {
    window.clearTimeout(pdfInitTimeoutId);
  }
  pdfInitTimeoutId = window.setTimeout(() => {
    if (loading.value) {
      usingFallbackPreview.value = true;
      loading.value = false;
      renderError.value = 'PDF.js 初始化超时。';
    }
  }, 25000);

  try {
    const task = getDocument({
      url: props.pdfUrl,
      withCredentials: false,
    });

    // PDF.js 的类实例包含私有字段，必须避免被 Vue reactive proxy 包装。
    pdfDocument.value = markRaw(await task.promise);
    totalPages.value = pdfDocument.value.numPages;
    currentPage.value = Math.min(Math.max(props.targetPage, 1), totalPages.value);
    await renderPage(currentPage.value);
  } catch (error) {
    pdfDocument.value = null;
    usingFallbackPreview.value = true;
    loading.value = false;
    renderError.value = error instanceof Error ? error.message : 'PDF.js 初始化失败。';
  } finally {
    if (pdfInitTimeoutId !== null) {
      window.clearTimeout(pdfInitTimeoutId);
      pdfInitTimeoutId = null;
    }
  }
}

function goToPage(pageNo: number) {
  const nextPage = Math.min(Math.max(pageNo, 1), totalPages.value);
  if (nextPage === currentPage.value) {
    emit('page-change', nextPage);
    return;
  }

  currentPage.value = nextPage;
  void renderPage(nextPage);
}

function adjustScale(delta: number) {
  const nextScale = Math.min(Math.max(scale.value + delta, 0.75), 2.4);
  if (nextScale === scale.value) {
    return;
  }

  scale.value = Number(nextScale.toFixed(2));
  void renderPage(currentPage.value);
}

function matchSelectionToBlock(selectedText: string): ParsedDocumentBlock | null {
  const normalized = selectedText.trim().toLowerCase();
  if (!normalized) {
    return null;
  }

  const candidateFromDom = document.activeElement instanceof HTMLElement
    ? document.activeElement.closest<HTMLElement>('[data-block-id]')
    : null;
  if (candidateFromDom) {
    const blockId = candidateFromDom.dataset.blockId ?? '';
    return blockById.value[blockId] ?? null;
  }

  return currentPageBlocks.value.find((block) => {
    const blockText = normalizeBlockDisplayText(block.text).toLowerCase();
    return blockText.includes(normalized) || normalized.includes(blockText.slice(0, Math.min(blockText.length, 48)));
  }) ?? currentPageBlocks.value[0] ?? null;
}

function handleBlockTextSelection() {
  const selection = window.getSelection();
  const selectedText = selection?.toString().trim() ?? '';

  if (!selectedText) {
    return;
  }

  const anchorNode = selection?.anchorNode;
  const anchorElement = anchorNode instanceof HTMLElement
    ? anchorNode
    : anchorNode?.parentElement ?? null;
  const blockElement = anchorElement?.closest<HTMLElement>('[data-block-id]') ?? null;
  const blockId = blockElement?.dataset.blockId ?? null;
  const block = (blockId ? blockById.value[blockId] : null) ?? matchSelectionToBlock(selectedText);

  emit('selection-change', {
    pageNo: currentPage.value,
    blockId: block?.block_id ?? null,
    paragraphNo: block?.paragraph_no ?? null,
    selectedText,
  });
}

watch(
  () => props.targetPage,
  (pageNo) => {
    if (pageNo > 0 && pageNo !== currentPage.value) {
      goToPage(pageNo);
    }
  },
);

watch(
  () => props.targetBlockId,
  async () => {
    await nextTick();
    const blockId = props.targetBlockId;
    if (!blockId || !blockTextLayerRef.value) {
      return;
    }

    const target = blockTextLayerRef.value.querySelector<HTMLElement>(`[data-block-id="${blockId}"]`);
    target?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  },
);

watch(
  () => props.pdfUrl,
  () => {
    void openDocument();
  },
);

onMounted(() => {
  void openDocument();
});
</script>

<template>
  <section class="reader-panel">
    <header class="reader-toolbar">
      <div>
        <p class="page-kicker">Reader / Spec 05</p>
        <strong>第 {{ currentPage }} / {{ totalPages }} 页</strong>
      </div>

      <div class="reader-toolbar__actions">
        <button class="toolbar-button toolbar-button--ghost" type="button" @click="goToPage(currentPage - 1)">
          上一页
        </button>
        <button class="toolbar-button toolbar-button--ghost" type="button" @click="goToPage(currentPage + 1)">
          下一页
        </button>
        <button class="toolbar-button toolbar-button--ghost" type="button" @click="adjustScale(-0.1)">
          缩小
        </button>
        <button class="toolbar-button toolbar-button--ghost" type="button" @click="adjustScale(0.1)">
          放大
        </button>
      </div>
    </header>

    <div class="reader-stage">
      <div class="reader-canvas-shell">
        <div v-if="usingFallbackPreview" class="reader-fallback">
          <iframe :src="`${pdfUrl}#page=${currentPage}&zoom=${Math.round(scale * 100)}`" title="PDF preview" />
        </div>

        <div v-else class="reader-page-layer">
          <canvas ref="canvasRef" class="reader-canvas" />
          <div ref="textLayerRef" class="reader-text-layer" />
        </div>

        <div v-if="loading" class="reader-overlay">
          <p>正在加载 PDF 页面...</p>
        </div>
      </div>

      <div class="reader-meta">
        <div class="reader-status-card">
          <span class="toolbar-label">缩放</span>
          <strong>{{ Math.round(scale * 100) }}%</strong>
        </div>
        <div class="reader-status-card">
          <span class="toolbar-label">定位策略</span>
          <strong>{{ selectedBlockContext ? selectedBlockContext.block_id : '页级定位' }}</strong>
        </div>
      </div>
    </div>

    <p v-if="renderError" class="workspace-parse-error">
      {{ usingFallbackPreview ? `PDF.js 不可用，已退回原生预览：${renderError}` : renderError }}
    </p>

    <section class="reader-block-layer">
      <header class="reader-block-layer__header">
        <div>
          <p class="page-kicker">Selectable Block Layer</p>
          <h2>当前页文本块</h2>
        </div>
        <p class="reader-hint">首期锚点按 block 归属，选区默认绑定到起始块。</p>
      </header>

      <div ref="blockTextLayerRef" class="reader-block-list" @mouseup="handleBlockTextSelection">
        <article
          v-for="block in currentPageBlocks"
          :key="block.block_id"
          class="reader-block-card"
          :class="{ 'reader-block-card--active': block.block_id === targetBlockId }"
          :data-block-id="block.block_id"
        >
          <div class="reader-block-card__meta">
            <span>{{ block.block_id }}</span>
            <span>¶ {{ block.paragraph_no ?? '-' }}</span>
            <span>{{ block.type }}</span>
          </div>
          <div class="reader-block-card__content" v-html="renderBlockHtml(block)" />
        </article>
      </div>
    </section>
  </section>
</template>
