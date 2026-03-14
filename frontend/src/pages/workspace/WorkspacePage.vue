<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import {
  createAssetNote,
  createAssetChatSession,
  deleteNote,
  fetchAssetNotes,
  fetchAssetChatSessions,
  fetchAssetDetail,
  fetchAssetMindmap,
  fetchAssetParseStatus,
  fetchAssetParsedDocument,
  fetchChatSessionMessages,
  fetchAssetPdfMeta,
  getAssetPdfUrl,
  previewAnchor,
  rebuildAssetMindmap,
  retryAssetParse,
  sendChatSessionMessage,
  updateNote,
  type AnchorPreviewResponse,
  type AssetDetail,
  type AssetMindmapResponse,
  type AssetParseStatusResponse,
  type AssetParsedDocumentResponse,
  type AssetPdfDescriptor,
  type ChatCitationItem,
  type ChatMessageItem,
  type ChatSessionItem,
  type MindmapNodeItem,
  type NoteAnchorType,
  type NoteItem,
  type NoteListResponse,
  type ParsedDocumentBlock,
} from '@/api/assets';
import MindmapPanel from '@/components/MindmapPanel.vue';
import PdfReaderPanel from '@/components/PdfReaderPanel.vue';
import { renderMarkdownToSafeHtml } from '@/utils/markdown';
import { normalizeBlockDisplayText } from '@/utils/text';

const route = useRoute();
const assetId = computed(() => route.params.assetId as string);

const asset = ref<AssetDetail | null>(null);
const parseStatus = ref<AssetParseStatusResponse | null>(null);
const parsedDocumentResponse = ref<AssetParsedDocumentResponse | null>(null);
const pdfMeta = ref<AssetPdfDescriptor | null>(null);
const mindmapData = ref<AssetMindmapResponse | null>(null);
const loading = ref(true);
const errorMessage = ref('');
const resourceWarning = ref('');
const mindmapError = ref('');
const retrying = ref(false);
const rebuildingMindmap = ref(false);
const anchorError = ref('');
const anchorPreview = ref<AnchorPreviewResponse | null>(null);
const selectedTextSnippet = ref('');
const targetPage = ref(1);
const targetBlockId = ref<string | null>(null);
const chatSessions = ref<ChatSessionItem[]>([]);
const activeSessionId = ref<string | null>(null);
const sessionMessages = ref<ChatMessageItem[]>([]);
const chatQuestion = ref('');
const chatError = ref('');
const chatLoading = ref(false);
const chatSubmitting = ref(false);
const creatingSession = ref(false);
const notes = ref<NoteItem[]>([]);
const notesLoading = ref(false);
const notesError = ref('');
const noteFormError = ref('');
const noteSubmitting = ref(false);
const noteDeletingId = ref<string | null>(null);
const noteFilter = ref<'all' | NoteAnchorType>('all');
const noteAnchorMode = ref<'text_selection' | 'mindmap_node'>('text_selection');
const noteFormTitle = ref('');
const noteFormContent = ref('');
const editingNoteId = ref<string | null>(null);
const selectedMindmapNode = ref<MindmapNodeItem | null>(null);
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
const activeSession = computed(() => chatSessions.value.find((item) => item.id === activeSessionId.value) ?? null);
const noteFilterValue = computed<NoteAnchorType | undefined>(() =>
  noteFilter.value === 'all' ? undefined : noteFilter.value,
);

const canRenderReader = computed(() => Boolean(asset.value && pdfMeta.value));
const canAskQuestion = computed(() => (asset.value?.basic_resources.kb_status ?? '') === 'ready');
const shouldPollWorkspace = computed(() => {
  const parseInProgress = parseStatus.value ? ['queued', 'processing'].includes(parseStatus.value.parse_status) : false;
  const mindmapInProgress = (asset.value?.basic_resources.mindmap_status ?? '') === 'processing';
  return parseInProgress || mindmapInProgress;
});

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

const currentAnchorHint = computed(() => {
  if (noteAnchorMode.value === 'mindmap_node') {
    if (!selectedMindmapNode.value) {
      return '点击导图节点后，可按节点锚点创建笔记。';
    }
    return `当前导图节点：${selectedMindmapNode.value.title}`;
  }
  if (!anchorPreview.value) {
    return '在阅读器中选中文本后，可按 text_selection 锚点创建笔记。';
  }
  return `当前选区：P${anchorPreview.value.page_no} / ${anchorPreview.value.block_id}`;
});

function normalizeErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

function stopParsePolling() {
  if (parsePollTimer !== null) {
    window.clearInterval(parsePollTimer);
    parsePollTimer = null;
  }
}

function syncParsePolling() {
  stopParsePolling();

  if (!shouldPollWorkspace.value) {
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
  resourceWarning.value = '';
  chatError.value = '';
  mindmapError.value = '';

  try {
    const [assetDetail, latestParseStatus] = await Promise.all([
      fetchAssetDetail(assetId.value),
      fetchAssetParseStatus(assetId.value),
    ]);

    asset.value = assetDetail;
    parseStatus.value = latestParseStatus;
    parsedDocumentResponse.value = null;
    pdfMeta.value = null;
    mindmapData.value = null;

    const [parsedDocumentResult, pdfMetaResult, mindmapResult] = await Promise.allSettled([
      fetchAssetParsedDocument(assetId.value),
      fetchAssetPdfMeta(assetId.value),
      fetchAssetMindmap(assetId.value),
    ]);
    const warnings: string[] = [];

    if (parsedDocumentResult.status === 'fulfilled') {
      parsedDocumentResponse.value = parsedDocumentResult.value;
    } else {
      warnings.push('解析索引加载失败');
    }

    if (pdfMetaResult.status === 'fulfilled') {
      pdfMeta.value = pdfMetaResult.value;
    } else {
      warnings.push('PDF 资源加载失败');
    }

    if (mindmapResult.status === 'fulfilled') {
      mindmapData.value = mindmapResult.value;
    } else {
      mindmapError.value = '导图加载失败';
    }

    resourceWarning.value = warnings.join('；');
    const initialPage = parsedDocumentResponse.value?.parsed_json?.pages[0]?.page_no ?? 1;
    if (!targetBlockId.value) {
      targetPage.value = initialPage;
    }

    await Promise.all([loadChatSessions(), loadNotes()]);
  } catch (error) {
    errorMessage.value = normalizeErrorMessage(error, '工作区加载失败。');
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
    errorMessage.value = normalizeErrorMessage(error, '重新解析失败。');
  } finally {
    retrying.value = false;
  }
}

async function handleRebuildMindmap() {
  rebuildingMindmap.value = true;
  mindmapError.value = '';
  try {
    await rebuildAssetMindmap(assetId.value);
    await loadWorkspace();
  } catch (error) {
    mindmapError.value = normalizeErrorMessage(error, '重建导图失败。');
  } finally {
    rebuildingMindmap.value = false;
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
    noteAnchorMode.value = 'text_selection';
    focusPage(response.page_no, response.block_id);
  } catch (error) {
    anchorError.value = normalizeErrorMessage(error, '锚点生成失败。');
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

async function loadSessionMessages(sessionId: string) {
  chatLoading.value = true;
  chatError.value = '';

  try {
    const response = await fetchChatSessionMessages(sessionId);
    if (activeSessionId.value === sessionId) {
      sessionMessages.value = response.messages;
    }
  } catch (error) {
    chatError.value = normalizeErrorMessage(error, '会话消息加载失败。');
    sessionMessages.value = [];
  } finally {
    chatLoading.value = false;
  }
}

async function loadChatSessions() {
  try {
    const sessions = await fetchAssetChatSessions(assetId.value);
    chatSessions.value = sessions;
    const hasActiveSession =
      activeSessionId.value !== null && sessions.some((session) => session.id === activeSessionId.value);
    if (!hasActiveSession) {
      activeSessionId.value = sessions[0]?.id ?? null;
    }

    if (activeSessionId.value) {
      await loadSessionMessages(activeSessionId.value);
    } else {
      sessionMessages.value = [];
    }
  } catch (error) {
    chatError.value = normalizeErrorMessage(error, '会话列表加载失败。');
    chatSessions.value = [];
    activeSessionId.value = null;
    sessionMessages.value = [];
  }
}

async function handleCreateSession() {
  if (!asset.value) {
    return;
  }

  creatingSession.value = true;
  chatError.value = '';

  try {
    const createdSession = await createAssetChatSession(assetId.value);
    chatSessions.value = [createdSession, ...chatSessions.value];
    activeSessionId.value = createdSession.id;
    sessionMessages.value = [];
  } catch (error) {
    chatError.value = normalizeErrorMessage(error, '创建会话失败。');
  } finally {
    creatingSession.value = false;
  }
}

async function handleAskQuestion() {
  const sessionId = activeSessionId.value;
  const question = chatQuestion.value.trim();
  if (!sessionId || !question || chatSubmitting.value) {
    return;
  }

  chatSubmitting.value = true;
  chatError.value = '';

  try {
    await sendChatSessionMessage(sessionId, {
      question,
      selected_anchor: anchorPreview.value
        ? {
            page_no: anchorPreview.value.page_no,
            block_id: anchorPreview.value.block_id,
            paragraph_no: anchorPreview.value.paragraph_no,
            selected_text: anchorPreview.value.selected_text,
            selector_type: anchorPreview.value.selector_type,
            selector_payload: anchorPreview.value.selector_payload,
          }
        : undefined,
      top_k: 6,
    });
    chatQuestion.value = '';

    chatSessions.value = chatSessions.value.map((session) =>
      session.id === sessionId
        ? {
            ...session,
            message_count: session.message_count + 2,
          }
        : session,
    );
    await loadSessionMessages(sessionId);
  } catch (error) {
    chatError.value = normalizeErrorMessage(error, '提问失败，请稍后重试。');
  } finally {
    chatSubmitting.value = false;
  }
}

function handleSessionChange(event: Event) {
  const selected = (event.target as HTMLSelectElement).value;
  activeSessionId.value = selected || null;
  if (activeSessionId.value) {
    void loadSessionMessages(activeSessionId.value);
    return;
  }
  sessionMessages.value = [];
}

function formatMessageRole(role: string): string {
  return role === 'assistant' ? '助教' : '你';
}

function formatMessageTime(createdAt: string): string {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    return createdAt;
  }
  return date.toLocaleString();
}

function formatCitationSection(sectionPath: string[]): string {
  if (!sectionPath.length) {
    return '未标注章节';
  }
  return sectionPath.join(' / ');
}

function formatCitationPage(citation: ChatCitationItem): string {
  if (citation.page_start !== null && citation.page_end !== null) {
    return citation.page_start === citation.page_end
      ? `P${citation.page_start}`
      : `P${citation.page_start}-${citation.page_end}`;
  }
  if (citation.page_start !== null) {
    return `P${citation.page_start}`;
  }
  if (citation.page_end !== null) {
    return `P${citation.page_end}`;
  }
  return '页码未知';
}

function jumpToCitation(citation: ChatCitationItem) {
  const preferredBlockId = citation.block_ids[0] ?? null;
  const preferredPage = citation.page_start ?? citation.page_end;

  if (preferredPage !== null) {
    focusPage(preferredPage, preferredBlockId);
    return;
  }

  if (!preferredBlockId) {
    return;
  }

  const block = blockById.value[preferredBlockId];
  if (!block) {
    return;
  }
  focusPage(block.page_no, preferredBlockId);
}

function handleMindmapNodeClick(node: MindmapNodeItem) {
  selectedMindmapNode.value = node;
  noteAnchorMode.value = 'mindmap_node';
  const preferredBlockId = node.block_ids[0] ?? null;
  if (node.page_no !== null) {
    focusPage(node.page_no, preferredBlockId);
    return;
  }
  if (!preferredBlockId) {
    return;
  }
  const block = blockById.value[preferredBlockId];
  if (!block) {
    return;
  }
  focusPage(block.page_no, preferredBlockId);
}

function resolveNoteAnchorPage(note: NoteItem): number | null {
  if (note.anchor.page_no !== null) {
    return note.anchor.page_no;
  }
  if (!note.anchor.block_id) {
    return null;
  }
  return blockById.value[note.anchor.block_id]?.page_no ?? null;
}

function applyTextAnchorFromNote(note: NoteItem, pageNo: number | null) {
  const blockId = note.anchor.block_id;
  if (pageNo === null || !blockId) {
    return;
  }

  anchorPreview.value = {
    asset_id: assetId.value,
    page_no: pageNo,
    block_id: blockId,
    paragraph_no: note.anchor.paragraph_no,
    selected_text: note.anchor.selected_text ?? note.content.slice(0, 120),
    selector_type: note.anchor.selector_type,
    selector_payload: note.anchor.selector_payload,
  };
  selectedTextSnippet.value = note.anchor.selected_text ?? '';
}

function jumpToNote(note: NoteItem) {
  const pageNo = resolveNoteAnchorPage(note);
  const blockId = note.anchor.block_id;

  if (pageNo !== null) {
    focusPage(pageNo, blockId);
  } else if (blockId) {
    const block = blockById.value[blockId];
    if (block) {
      focusPage(block.page_no, blockId);
    }
  }

  if (note.anchor.anchor_type === 'mindmap_node') {
    noteAnchorMode.value = 'mindmap_node';
  } else {
    noteAnchorMode.value = 'text_selection';
    applyTextAnchorFromNote(note, pageNo);
  }
}

function formatNoteTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function formatNoteAnchor(note: NoteItem): string {
  const anchor = note.anchor;
  if (anchor.anchor_type === 'mindmap_node') {
    const nodeKey = anchor.selector_payload.node_key;
    const readableKey = typeof nodeKey === 'string' && nodeKey.trim() ? nodeKey : 'unknown';
    const pageLabel = anchor.page_no !== null ? `P${anchor.page_no}` : '页码未知';
    return `导图节点 ${readableKey} · ${pageLabel}`;
  }
  const pageLabel = anchor.page_no !== null ? `P${anchor.page_no}` : '页码未知';
  const blockLabel = anchor.block_id ?? '页级定位';
  return `${anchor.anchor_type} · ${pageLabel} / ${blockLabel}`;
}

function buildNoteAnchorPayload() {
  if (noteAnchorMode.value === 'mindmap_node') {
    const node = selectedMindmapNode.value;
    if (!node) {
      throw new Error('请先点击导图节点，再创建导图锚点笔记。');
    }
    const preferredBlockId = node.block_ids[0] ?? null;
    return {
      anchor_type: 'mindmap_node' as const,
      page_no: node.page_no,
      block_id: preferredBlockId,
      selector_type: 'mindmap_node',
      selector_payload: {
        node_key: node.node_key,
        block_id: preferredBlockId,
      },
    };
  }

  if (!anchorPreview.value) {
    throw new Error('请先在阅读器中选中文本，再创建文本锚点笔记。');
  }
  return {
    anchor_type: 'text_selection' as const,
    page_no: anchorPreview.value.page_no,
    block_id: anchorPreview.value.block_id,
    paragraph_no: anchorPreview.value.paragraph_no,
    selected_text: anchorPreview.value.selected_text,
    selector_type: anchorPreview.value.selector_type,
    selector_payload: anchorPreview.value.selector_payload,
  };
}

function resetNoteForm() {
  editingNoteId.value = null;
  noteFormTitle.value = '';
  noteFormContent.value = '';
  noteFormError.value = '';
}

function handleEditNote(note: NoteItem) {
  editingNoteId.value = note.id;
  noteFormTitle.value = note.title ?? '';
  noteFormContent.value = note.content;
  noteFormError.value = '';
  jumpToNote(note);
}

function cancelEditNote() {
  resetNoteForm();
}

async function loadNotes() {
  notesLoading.value = true;
  notesError.value = '';
  try {
    const response: NoteListResponse = await fetchAssetNotes(assetId.value, noteFilterValue.value);
    notes.value = response.notes;
  } catch (error) {
    notesError.value = normalizeErrorMessage(error, '笔记列表加载失败。');
    notes.value = [];
  } finally {
    notesLoading.value = false;
  }
}

async function handleSubmitNote() {
  const content = noteFormContent.value.trim();
  if (!content) {
    noteFormError.value = '笔记内容不能为空。';
    return;
  }
  if (noteSubmitting.value) {
    return;
  }

  noteSubmitting.value = true;
  noteFormError.value = '';

  try {
    if (editingNoteId.value) {
      await updateNote(editingNoteId.value, {
        title: noteFormTitle.value.trim() || null,
        content,
      });
    } else {
      await createAssetNote(assetId.value, {
        anchor: buildNoteAnchorPayload(),
        title: noteFormTitle.value.trim() || null,
        content,
      });
    }
    resetNoteForm();
    await loadNotes();
  } catch (error) {
    noteFormError.value = normalizeErrorMessage(error, '保存笔记失败。');
  } finally {
    noteSubmitting.value = false;
  }
}

async function handleDeleteNote(note: NoteItem) {
  if (noteDeletingId.value) {
    return;
  }
  const confirmed = window.confirm('确认删除这条笔记吗？');
  if (!confirmed) {
    return;
  }

  noteDeletingId.value = note.id;
  notesError.value = '';
  try {
    await deleteNote(note.id);
    if (editingNoteId.value === note.id) {
      resetNoteForm();
    }
    await loadNotes();
  } catch (error) {
    notesError.value = normalizeErrorMessage(error, '删除笔记失败。');
  } finally {
    noteDeletingId.value = null;
  }
}

watch(
  () => noteFilter.value,
  () => {
    void loadNotes();
  },
);

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
          <p class="page-kicker">Workspace / Spec 09</p>
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
          <p v-if="resourceWarning" class="workspace-parse-error">
            {{ resourceWarning }}。你可以先查看状态并重试解析。
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
              <MindmapPanel
                :mindmap-data="mindmapData"
                :loading="false"
                :error-message="mindmapError"
                :rebuilding="rebuildingMindmap"
                @node-click="handleMindmapNodeClick"
                @rebuild="handleRebuildMindmap"
              />
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
                  <p class="page-kicker">Notes</p>
                  <h2>锚点笔记</h2>
                </div>
                <select v-model="noteFilter" class="workspace-notes-filter">
                  <option value="all">全部锚点</option>
                  <option value="text_selection">文本锚点</option>
                  <option value="mindmap_node">导图锚点</option>
                  <option value="knowledge_point">知识点锚点</option>
                </select>
              </header>

              <div class="workspace-note-anchor-switch">
                <button
                  class="workspace-note-anchor-button"
                  :class="{ 'workspace-note-anchor-button--active': noteAnchorMode === 'text_selection' }"
                  type="button"
                  @click="noteAnchorMode = 'text_selection'"
                >
                  选区锚点
                </button>
                <button
                  class="workspace-note-anchor-button"
                  :class="{ 'workspace-note-anchor-button--active': noteAnchorMode === 'mindmap_node' }"
                  type="button"
                  @click="noteAnchorMode = 'mindmap_node'"
                >
                  导图锚点
                </button>
              </div>

              <p class="workspace-note-anchor-hint">{{ currentAnchorHint }}</p>

              <div class="workspace-note-form">
                <input
                  v-model="noteFormTitle"
                  class="workspace-note-input"
                  type="text"
                  placeholder="笔记标题（可选）"
                >
                <textarea
                  v-model="noteFormContent"
                  class="workspace-note-textarea"
                  rows="4"
                  placeholder="输入你的笔记内容（支持 Markdown 纯文本）"
                />
              </div>

              <div class="workspace-actions">
                <button
                  class="toolbar-button"
                  type="button"
                  :disabled="noteSubmitting || !noteFormContent.trim()"
                  @click="handleSubmitNote"
                >
                  {{ noteSubmitting ? '保存中...' : (editingNoteId ? '保存修改' : '创建笔记') }}
                </button>
                <button
                  v-if="editingNoteId"
                  class="toolbar-button toolbar-button--ghost"
                  type="button"
                  :disabled="noteSubmitting"
                  @click="cancelEditNote"
                >
                  取消编辑
                </button>
              </div>

              <p v-if="noteFormError" class="workspace-parse-error">
                {{ noteFormError }}
              </p>
              <p v-if="notesError" class="workspace-parse-error">
                {{ notesError }}
              </p>

              <div class="workspace-note-list">
                <p v-if="notesLoading" class="workspace-muted">正在加载笔记...</p>
                <p v-else-if="notes.length === 0" class="workspace-muted">当前资产还没有笔记，先从选区或导图节点创建一条。</p>

                <article
                  v-for="note in notes"
                  :key="note.id"
                  class="workspace-note-item"
                >
                  <header class="workspace-note-item__header">
                    <strong>{{ note.title || '未命名笔记' }}</strong>
                    <span>{{ formatNoteTime(note.updated_at) }}</span>
                  </header>
                  <p class="workspace-note-item__anchor">{{ formatNoteAnchor(note) }}</p>
                  <p class="workspace-note-item__content">{{ note.content }}</p>
                  <p v-if="note.anchor.selected_text" class="workspace-note-item__quote">{{ note.anchor.selected_text }}</p>
                  <div class="workspace-note-item__actions">
                    <button class="toolbar-button toolbar-button--ghost" type="button" @click="jumpToNote(note)">
                      回跳
                    </button>
                    <button class="toolbar-button toolbar-button--ghost" type="button" @click="handleEditNote(note)">
                      编辑
                    </button>
                    <button
                      class="toolbar-button"
                      type="button"
                      :disabled="noteDeletingId === note.id"
                      @click="handleDeleteNote(note)"
                    >
                      {{ noteDeletingId === note.id ? '删除中...' : '删除' }}
                    </button>
                  </div>
                </article>
              </div>
            </section>

            <section class="workspace-panel">
              <header class="workspace-panel__header">
                <div>
                  <p class="page-kicker">Tutor</p>
                  <h2>问答面板</h2>
                </div>
              </header>

              <div class="workspace-chat-toolbar">
                <button
                  class="toolbar-button toolbar-button--ghost"
                  type="button"
                  :disabled="creatingSession"
                  @click="handleCreateSession"
                >
                  {{ creatingSession ? '创建中...' : '新建会话' }}
                </button>
                <select
                  class="workspace-chat-select"
                  :value="activeSessionId ?? ''"
                  @change="handleSessionChange"
                >
                  <option value="">请选择会话</option>
                  <option
                    v-for="(session, index) in chatSessions"
                    :key="session.id"
                    :value="session.id"
                  >
                    {{ `#${index + 1} ${session.title}` }}
                  </option>
                </select>
              </div>

              <p v-if="activeSession" class="workspace-chat-session-meta">
                当前会话：{{ activeSession.title }} · 消息 {{ activeSession.message_count }}
              </p>

              <p v-if="!canAskQuestion" class="workspace-muted">
                当前资产知识库未就绪，暂时无法发起问答。
              </p>

              <div class="workspace-chat-form">
                <textarea
                  v-model="chatQuestion"
                  class="workspace-chat-input"
                  placeholder="输入你想问的问题，例如：本文方法与 Transformer 的核心差异是什么？"
                  rows="3"
                  :disabled="!activeSessionId || !canAskQuestion || chatSubmitting"
                />
                <button
                  class="toolbar-button"
                  type="button"
                  :disabled="!activeSessionId || !canAskQuestion || chatSubmitting || !chatQuestion.trim()"
                  @click="handleAskQuestion"
                >
                  {{ chatSubmitting ? '提问中...' : '发送问题' }}
                </button>
              </div>

              <p v-if="chatError" class="workspace-parse-error">
                {{ chatError }}
              </p>

              <div class="workspace-chat-thread">
                <p v-if="chatLoading" class="workspace-muted">
                  正在加载会话消息...
                </p>
                <p v-else-if="activeSessionId && sessionMessages.length === 0" class="workspace-muted">
                  当前会话还没有消息，输入问题后将生成回答和引用。
                </p>
                <p v-else-if="!activeSessionId" class="workspace-muted">
                  请先创建或选择一个会话。
                </p>

                <article
                  v-for="message in sessionMessages"
                  :key="message.id"
                  class="workspace-chat-message"
                  :class="{ 'workspace-chat-message--assistant': message.role === 'assistant' }"
                >
                  <header class="workspace-chat-message__header">
                    <strong>{{ formatMessageRole(message.role) }}</strong>
                    <span>{{ formatMessageTime(message.created_at) }}</span>
                  </header>
                  <p class="workspace-chat-message__content">{{ message.content }}</p>

                  <ul
                    v-if="message.role === 'assistant' && message.citations.length"
                    class="workspace-citation-list"
                  >
                    <li
                      v-for="citation in message.citations"
                      :key="citation.citation_id"
                    >
                      <button
                        class="workspace-citation-item"
                        type="button"
                        @click="jumpToCitation(citation)"
                      >
                        <span class="workspace-citation-item__title">{{ formatCitationSection(citation.section_path) }}</span>
                        <span class="workspace-citation-item__meta">
                          {{ formatCitationPage(citation) }} · 相似度 {{ citation.score.toFixed(2) }}
                        </span>
                        <p>{{ citation.quote_text }}</p>
                      </button>
                    </li>
                  </ul>
                </article>
              </div>
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
                <li>导图状态：{{ mindmapData?.mindmap_status ?? asset.basic_resources.mindmap_status }}</li>
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
