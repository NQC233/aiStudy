<script setup lang="ts">
import { computed } from 'vue';

import type { AssetListItem } from '@/api/assets';

const props = defineProps<{
  asset: AssetListItem;
}>();

const statusLabel = computed(() => {
  const mapping: Record<string, string> = {
    draft: '草稿',
    processing: '处理中',
    ready: '可学习',
    failed: '失败',
  };

  return mapping[props.asset.status] ?? props.asset.status;
});

const sourceLabel = computed(() => {
  return props.asset.source_type === 'preset' ? '预设论文' : '用户上传';
});

const createdAtLabel = computed(() => {
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(props.asset.created_at));
});
</script>

<template>
  <article class="asset-card">
    <div class="asset-card__topline">
      <span class="asset-card__source">{{ sourceLabel }}</span>
      <span class="asset-card__date">{{ createdAtLabel }}</span>
    </div>

    <h3 class="asset-card__title">{{ asset.title }}</h3>
    <p class="asset-card__authors">{{ asset.authors.join(' · ') }}</p>

    <div class="asset-card__footer">
      <span class="asset-card__status" :data-status="asset.status">
        {{ statusLabel }}
      </span>
      <slot />
    </div>
  </article>
</template>
