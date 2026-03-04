<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

import { fetchAssetDetail, type AssetDetail } from '@/api/assets';

const route = useRoute();
const asset = ref<AssetDetail | null>(null);
const loading = ref(true);
const errorMessage = ref('');

const placeholderModules = computed(() => {
  if (asset.value === null) {
    return [];
  }

  return [
    ['阅读器', asset.value.basic_resources.parse_status],
    ['问答区', asset.value.basic_resources.kb_status],
    ['思维导图', asset.value.basic_resources.mindmap_status],
    ['笔记区', '未接入'],
  ];
});

async function loadAssetDetail() {
  loading.value = true;
  errorMessage.value = '';

  try {
    asset.value = await fetchAssetDetail(route.params.assetId as string);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资产详情加载失败。';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadAssetDetail();
});
</script>

<template>
  <main class="workspace-page">
    <section class="workspace-shell">
      <header class="workspace-header">
        <div>
          <p class="page-kicker">Workspace / Spec 02</p>
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
              <li>解析状态：{{ asset.basic_resources.parse_status }}</li>
              <li>知识库状态：{{ asset.basic_resources.kb_status }}</li>
              <li>思维导图状态：{{ asset.basic_resources.mindmap_status }}</li>
            </ul>
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
