<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import {
  fetchAssetDetail,
  fetchAssetParseStatus,
  retryAssetParse,
  type AssetDetail,
  type AssetParseStatusResponse,
} from '@/api/assets';

const route = useRoute();
const asset = ref<AssetDetail | null>(null);
const parseStatus = ref<AssetParseStatusResponse | null>(null);
const loading = ref(true);
const errorMessage = ref('');
const retrying = ref(false);
let parsePollTimer: number | null = null;

const placeholderModules = computed(() => {
  if (asset.value === null) {
    return [];
  }

  return [
    ['阅读器', parseStatus.value?.parse_status ?? asset.value.basic_resources.parse_status],
    ['问答区', asset.value.basic_resources.kb_status],
    ['思维导图', asset.value.basic_resources.mindmap_status],
    ['笔记区', '未接入'],
  ];
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
    void loadParseStatus();
  }, 5000);
}

async function loadParseStatus() {
  parseStatus.value = await fetchAssetParseStatus(route.params.assetId as string);
  syncParsePolling();
}

async function loadAssetDetail() {
  loading.value = true;
  errorMessage.value = '';

  try {
    const [assetDetail, latestParseStatus] = await Promise.all([
      fetchAssetDetail(route.params.assetId as string),
      fetchAssetParseStatus(route.params.assetId as string),
    ]);
    asset.value = assetDetail;
    parseStatus.value = latestParseStatus;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资产详情加载失败。';
  } finally {
    loading.value = false;
    syncParsePolling();
  }
}

async function handleRetryParse() {
  retrying.value = true;
  errorMessage.value = '';

  try {
    await retryAssetParse(route.params.assetId as string);
    await loadAssetDetail();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '重新解析失败。';
  } finally {
    retrying.value = false;
  }
}

onMounted(() => {
  void loadAssetDetail();
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
          <p class="page-kicker">Workspace / Spec 04</p>
          <h1 v-if="asset">{{ asset.title }}</h1>
          <h1 v-else>资产工作区</h1>
        </div>

        <RouterLink to="/library" class="workspace-back">
          返回图书馆
        </RouterLink>
      </header>

      <section v-if="loading" class="workspace-empty">
        <h2>正在加载资产详情...</h2>
      </section>

      <section v-else-if="errorMessage" class="workspace-empty workspace-empty--error">
        <h2>{{ errorMessage }}</h2>
      </section>

      <template v-else-if="asset">
        <section class="workspace-summary">
          <div class="workspace-summary__lead">
            <span class="summary-badge">{{ asset.source_type === 'preset' ? '预设论文' : '用户上传' }}</span>
            <span class="summary-badge summary-badge--status">{{ asset.status }}</span>
          </div>

          <p class="workspace-authors">{{ asset.authors.join(' · ') }}</p>
          <p class="workspace-abstract">
            {{ asset.abstract || '当前资产还没有摘要内容，后续会由解析链路补充。' }}
          </p>
        </section>

        <section class="workspace-module-grid">
          <article
            v-for="[label, status] in placeholderModules"
            :key="label"
            class="workspace-module-card"
          >
            <p class="workspace-module-card__eyebrow">Module</p>
            <h2>{{ label }}</h2>
            <strong>{{ status }}</strong>
          </article>
        </section>

        <section class="workspace-resource-board">
          <div>
            <p class="page-kicker">基础资源状态</p>
            <ul class="resource-list">
              <li>解析状态：{{ parseStatus?.parse_status ?? asset.basic_resources.parse_status }}</li>
              <li>知识库状态：{{ asset.basic_resources.kb_status }}</li>
              <li>思维导图状态：{{ asset.basic_resources.mindmap_status }}</li>
            </ul>
          </div>

          <div>
            <p class="page-kicker">解析任务</p>
            <ul class="resource-list">
              <li>任务状态：{{ parseStatus?.latest_parse?.status ?? '尚未创建' }}</li>
              <li>MinerU 状态：{{ parseTaskLabel }}</li>
              <li>解析进度：{{ parseProgressLabel }}</li>
            </ul>

            <p v-if="parseStatus?.error_message" class="workspace-parse-error">
              {{ parseStatus.error_message }}
            </p>

            <div class="workspace-actions">
              <button class="toolbar-button toolbar-button--ghost" type="button" @click="loadParseStatus">
                刷新解析状态
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
          </div>

          <div>
            <p class="page-kicker">增强资源占位</p>
            <ul class="resource-list">
              <li>演示文稿：{{ asset.enhanced_resources.slides_status }}</li>
              <li>Anki：{{ asset.enhanced_resources.anki_status }}</li>
              <li>习题：{{ asset.enhanced_resources.quiz_status }}</li>
            </ul>
          </div>
        </section>
      </template>
    </section>
  </main>
</template>
