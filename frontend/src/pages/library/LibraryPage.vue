<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { useRouter } from 'vue-router';

import {
  deleteAsset,
  fetchAssets,
  type AssetListItem,
  type AssetUploadResponse,
} from '@/api/assets';
import AssetCard from '@/components/AssetCard.vue';
import UploadAssetDialog from '@/components/UploadAssetDialog.vue';

const router = useRouter();
const loading = ref(true);
const errorMessage = ref('');
const assets = ref<AssetListItem[]>([]);
const dialogOpen = ref(false);
const deletingAssetId = ref<string | null>(null);

const readyCount = computed(() => assets.value.filter((asset) => asset.status === 'ready').length);
const processingCount = computed(() => assets.value.filter((asset) => asset.status === 'processing').length);
const failedCount = computed(() => assets.value.filter((asset) => asset.status === 'failed').length);

async function loadAssets() {
  loading.value = true;
  errorMessage.value = '';

  try {
    assets.value = await fetchAssets();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资产列表加载失败。';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadAssets();
});

async function handleUploadSuccess(payload: AssetUploadResponse) {
  dialogOpen.value = false;
  await loadAssets();
  await router.push(`/workspace/${payload.asset.id}`);
}

async function handleDeleteAsset(asset: AssetListItem) {
  const confirmed = window.confirm(
    `确认删除资产《${asset.title}》吗？\n\n该操作会删除该资产的解析结果、知识库、问答、导图、笔记和演示数据。`,
  );
  if (!confirmed) {
    return;
  }

  deletingAssetId.value = asset.id;
  errorMessage.value = '';
  try {
    const response = await deleteAsset(asset.id);
    if (response.warning) {
      window.alert(`资产已删除，但存在清理提示：${response.warning}`);
    }
    await loadAssets();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '删除资产失败。';
  } finally {
    deletingAssetId.value = null;
  }
}
</script>

<template>
  <main class="library-page">
    <section class="library-hero">
      <div class="library-hero__copy">
        <p class="page-kicker">Library / Curated Intake</p>
        <h1>把论文资产整理成可进入工作流的学习入口</h1>
        <p class="page-intro">
          从这里统一查看上传资产、处理进度与可进入的学习工作区。Library 不再只是列表，而是整套产品体验的起点。
        </p>
      </div>

      <div class="library-hero__stats">
        <div class="stat-card">
          <span class="stat-card__label">资产总数</span>
          <strong>{{ assets.length }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">可进入工作区</span>
          <strong>{{ readyCount }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">处理中 / 失败</span>
          <strong>{{ processingCount }} / {{ failedCount }}</strong>
        </div>
      </div>
    </section>

    <section class="library-toolbar">
      <div>
        <span class="toolbar-label">Current shelf</span>
        <strong>个人图书馆 / 演示与学习资产入口</strong>
      </div>

      <div class="library-toolbar__actions">
        <button class="toolbar-button toolbar-button--ghost" type="button" @click="loadAssets">
          刷新列表
        </button>
        <button class="toolbar-button" type="button" @click="dialogOpen = true">
          上传论文
        </button>
      </div>
    </section>

    <section v-if="loading" class="empty-panel">
      <p class="page-kicker">Loading</p>
      <h2>正在整理你的学习资产...</h2>
    </section>

    <section v-else-if="errorMessage" class="empty-panel empty-panel--error">
      <p class="page-kicker">Request Error</p>
      <h2>{{ errorMessage }}</h2>
      <button class="toolbar-button" type="button" @click="loadAssets">
        重新请求
      </button>
    </section>

    <section v-else-if="assets.length === 0" class="empty-panel">
      <p class="page-kicker">Empty shelf</p>
      <h2>还没有学习资产</h2>
      <p class="page-intro">
        上传第一篇论文后，系统会继续为它生成解析、问答、导图与演示内容。
      </p>
      <button class="toolbar-button" type="button" @click="dialogOpen = true">
        立即上传
      </button>
    </section>

    <section v-else class="asset-grid">
      <AssetCard v-for="asset in assets" :key="asset.id" :asset="asset">
        <div class="asset-card__actions">
          <RouterLink :to="`/workspace/${asset.id}`" class="asset-card__action">
            进入工作区
          </RouterLink>
          <button
            class="asset-card__action asset-card__action--danger"
            type="button"
            :disabled="deletingAssetId === asset.id"
            @click="handleDeleteAsset(asset)"
          >
            {{ deletingAssetId === asset.id ? '删除中...' : '删除资产' }}
          </button>
        </div>
      </AssetCard>
    </section>

    <UploadAssetDialog
      v-if="dialogOpen"
      @close="dialogOpen = false"
      @success="handleUploadSuccess"
    />
  </main>
</template>
