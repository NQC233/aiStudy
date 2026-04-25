<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';

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

const deckViewport = ref<HTMLElement | null>(null);
const isFullscreen = ref(false);
const isFullscreenSupported = ref(false);

const activePage = computed(() => props.pages[props.currentIndex] ?? null);

function focusPage(index: number) {
  emit('update:currentIndex', index);
}

function syncFullscreenState() {
  if (typeof document === 'undefined') {
    isFullscreen.value = false;
    return;
  }
  isFullscreen.value = Boolean(deckViewport.value && document.fullscreenElement === deckViewport.value);
}

async function toggleFullscreen() {
  if (!isFullscreenSupported.value || typeof document === 'undefined') {
    return;
  }

  if (isFullscreen.value) {
    await document.exitFullscreen();
    return;
  }

  await deckViewport.value?.requestFullscreen();
}

onMounted(() => {
  isFullscreenSupported.value = Boolean(deckViewport.value?.requestFullscreen && document.exitFullscreen);
  document.addEventListener('fullscreenchange', syncFullscreenState);
  syncFullscreenState();
});

onUnmounted(() => {
  if (typeof document !== 'undefined') {
    document.removeEventListener('fullscreenchange', syncFullscreenState);
  }
});
</script>

<template>
  <div class="slides-deck-runtime">
    <div
      ref="deckViewport"
      class="slides-deck-runtime__viewport"
      :class="{ 'slides-deck-runtime__viewport--fullscreen': isFullscreen }"
    >
      <header class="slides-deck-runtime__toolbar">
        <button
          v-if="isFullscreenSupported"
          type="button"
          class="slides-deck-runtime__fullscreen-button"
          @click="toggleFullscreen"
        >
          {{ isFullscreen ? '退出全屏' : '进入全屏' }}
        </button>
      </header>

      <div class="slides-deck-runtime__frame-shell">
        <HtmlSlideFrame
          v-if="activePage"
          class="slides-deck-runtime__frame"
          :html="activePage.html"
          :css="activePage.css"
        />
      </div>

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
  </div>
</template>

<style scoped>
.slides-deck-runtime {
  display: grid;
}

.slides-deck-runtime__viewport {
  display: grid;
  gap: 0.75rem;
}

.slides-deck-runtime__viewport--fullscreen {
  min-height: 100vh;
  padding: 1rem;
  align-content: start;
  background: #161616;
}

.slides-deck-runtime__toolbar {
  display: flex;
  justify-content: flex-end;
}

.slides-deck-runtime__fullscreen-button {
  border: 1px solid #ab7c44;
  border-radius: 0.7rem;
  background: linear-gradient(135deg, #9a5f17, #6d4010);
  color: #fff;
  padding: 0.42rem 0.85rem;
  cursor: pointer;
}

.slides-deck-runtime__frame-shell {
  background: linear-gradient(180deg, #f9f5ec 0%, #f2ebe1 100%);
  border: 1px solid #e4dac7;
  border-radius: 1rem;
  padding: 0.8rem;
}

.slides-deck-runtime__viewport--fullscreen .slides-deck-runtime__frame-shell {
  min-height: calc(100vh - 8rem);
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 0;
  padding: 0;
}

.slides-deck-runtime__frame {
  width: 100%;
}

.slides-deck-runtime__viewport--fullscreen .slides-deck-runtime__frame {
  width: min(96vw, calc((100vh - 8rem) * 16 / 9));
  max-width: 100%;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.35);
}

.slides-deck-runtime__dots {
  display: flex;
  justify-content: center;
  gap: 0.4rem;
}

.slides-deck-runtime__viewport--fullscreen .slides-deck-runtime__dots {
  padding-bottom: 0.25rem;
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

.slides-deck-runtime__viewport--fullscreen .slides-deck-runtime__dot {
  border-color: rgba(255, 255, 255, 0.24);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.slides-deck-runtime__viewport--fullscreen .slides-deck-runtime__dot--active {
  border-color: #f2c078;
  background: rgba(242, 192, 120, 0.24);
}
</style>
