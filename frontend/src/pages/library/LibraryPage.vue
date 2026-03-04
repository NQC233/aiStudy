<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';

import { fetchAssets, type AssetListItem } from '@/api/assets';
import AssetCard from '@/components/AssetCard.vue';

const loading = ref(true);
const errorMessage = ref('');
const assets = ref<AssetListItem[]>([]);

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
</script>

<template>
  <main class="library-page">
    <section class="library-hero">
      <div class="library-hero__copy">
        <p class="page-kicker">Library / Spec 02</p>
        <h1>论文图书馆</h1>
        <p class="page-intro">
          这里先承接学习资产的基础展示与进入工作区的入口。当前仍是单用户开发模式，但所有数据结构都已经为多用户隔离预留字段。
        </p>
      </div>

      <div class="library-hero__stats">
        <div class="stat-card">
          <span class="stat-card__label">资产总数</span>
          <strong>{{ assets.length }}</strong>
        </div>
        <div class="stat-card">
          <span class="stat-card__label">当前阶段</span>
          <strong>Asset 骨架</strong>
        </div>
      </div>
    </section>

    <section class="library-toolbar">
      <div>
        <span class="toolbar-label">当前视图</span>
        <strong>个人图书馆 / 编辑部档案架</strong>
      </div>

      <button class="toolbar-button" type="button" @click="loadAssets">
        刷新列表
      </button>
    </section>

    <section v-if="loading" class="empty-panel">
      <p class="page-kicker">Loading</p>
      <h2>正在加载学习资产...</h2>
    </section>

    <section v-else-if="errorMessage" class="empty-panel empty-panel--error">
      <p class="page-kicker">Request Error</p>
      <h2>{{ errorMessage }}</h2>
      <button class="toolbar-button" type="button" @click="loadAssets">
        重新请求
      </button>
    </section>

    <section v-else class="asset-grid">
      <AssetCard v-for="asset in assets" :key="asset.id" :asset="asset">
        <RouterLink :to="`/workspace/${asset.id}`" class="asset-card__action">
          进入工作区
        </RouterLink>
      </AssetCard>
    </section>
  </main>
</template>
