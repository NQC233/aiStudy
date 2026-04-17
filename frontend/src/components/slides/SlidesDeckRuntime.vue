<script setup lang="ts">
import { computed } from 'vue';

import HtmlSlideFrame from '@/components/slides/HtmlSlideFrame.vue';

export interface RuntimeRenderedPage {
  page_id: string;
  html: string;
  css: string;
  asset_refs: unknown[];
  render_meta: Record<string, unknown>;
}

const props = defineProps<{
  pages: RuntimeRenderedPage[];
  currentIndex: number;
}>();

const emit = defineEmits<{
  (e: 'update:currentIndex', value: number): void;
}>();

const activePage = computed(() => props.pages[props.currentIndex] ?? null);

function focusPage(index: number) {
  emit('update:currentIndex', index);
}
</script>

<template>
  <div class="slides-deck-runtime">
    <HtmlSlideFrame v-if="activePage" :html="activePage.html" :css="activePage.css" />
    <nav v-if="pages.length > 1" class="slides-deck-runtime__dots" aria-label="Slide pages">
      <button
        v-for="(page, index) in pages"
        :key="page.page_id"
        type="button"
        class="slides-deck-runtime__dot"
        :class="{ 'slides-deck-runtime__dot--active': index === currentIndex }"
        @click="focusPage(index)"
      >
        {{ index + 1 }}
      </button>
    </nav>
  </div>
</template>

<style scoped>
.slides-deck-runtime {
  display: grid;
  gap: 0.75rem;
}

.slides-deck-runtime__dots {
  display: flex;
  justify-content: center;
  gap: 0.4rem;
}

.slides-deck-runtime__dot {
  border: 1px solid #dccfb6;
  border-radius: 999px;
  background: #fff9ef;
  color: #61401c;
  min-width: 2rem;
  padding: 0.2rem 0.55rem;
  cursor: pointer;
}

.slides-deck-runtime__dot--active {
  border-color: #8e5a22;
  background: #f6e7cf;
}
</style>
