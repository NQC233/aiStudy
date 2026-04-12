<script setup lang="ts">
import Reveal from 'reveal.js';
import RevealHighlight from 'reveal.js/plugin/highlight';
import RevealMath from 'reveal.js/plugin/math';
import RevealNotes from 'reveal.js/plugin/notes';
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';

import type { SlideDslBlock, SlideDslPage } from '@/api/assets';
import SafeSvgRenderer from '@/components/slides/SafeSvgRenderer.vue';
import { renderMarkdownToSafeHtml } from '@/utils/markdown';

import 'reveal.js/reveal.css';
import 'reveal.js/theme/white.css';
import 'reveal.js/plugin/highlight/monokai.css';

const props = defineProps<{
  pages: SlideDslPage[];
  currentIndex: number;
}>();

const emit = defineEmits<{
  (e: 'update:currentIndex', value: number): void;
}>();

const rootEl = ref<HTMLElement | null>(null);
let revealInstance: Reveal.Api | null = null;
let syncingFromReveal = false;

const currentPage = computed(() => props.pages[props.currentIndex] ?? null);

function blockByType(page: SlideDslPage | null, blockType: string): SlideDslBlock | null {
  if (!page) {
    return null;
  }
  return page.blocks.find((item) => item.block_type === blockType) ?? null;
}

function comparisonColumns(block: SlideDslBlock | null): string[] {
  const value = block?.meta?.columns;
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
    return value;
  }
  return ['方案', '说明', '结论'];
}

function comparisonRows(block: SlideDslBlock | null): string[][] {
  const value = block?.meta?.rows;
  if (Array.isArray(value)) {
    const rows = value
      .filter((row): row is unknown[] => Array.isArray(row))
      .map((row) => row.map((cell) => String(cell)));
    if (rows.length > 0) {
      return rows;
    }
  }
  return (block?.items ?? []).map((row) => row.split('｜').map((cell) => cell.trim()));
}

function flowSteps(block: SlideDslBlock | null): string[] {
  const value = block?.meta?.steps;
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
    return value;
  }
  return block?.items ?? [];
}

function richText(block: SlideDslBlock | null): string {
  if (!block) {
    return '';
  }
  const raw = block.content?.trim() ? block.content : (block.items ?? []).join('\n');
  return renderMarkdownToSafeHtml(raw || '');
}

function keyPointClass(page: SlideDslPage): string {
  if (page.animation_preset === 'stagger_reveal') {
    return 'fragment fade-up';
  }
  return '';
}

function layoutClass(page: SlideDslPage): string {
  return `layout-${(page.layout_hint || 'hero-left').replace(/[^a-z0-9-]/gi, '').toLowerCase()}`;
}

function toneClass(page: SlideDslPage): string {
  return `tone-${(page.visual_tone || 'technical').replace(/[^a-z0-9-]/gi, '').toLowerCase()}`;
}

async function initReveal() {
  if (!rootEl.value) {
    return;
  }

  await nextTick();
  const deck = rootEl.value.querySelector('.reveal') as HTMLElement | null;
  if (!deck) {
    return;
  }

  revealInstance = new Reveal(deck, {
    embedded: true,
    controls: true,
    progress: true,
    center: false,
    hash: false,
    width: 1280,
    height: 720,
    margin: 0.02,
    transition: 'slide',
    transitionSpeed: 'default',
    plugins: [RevealNotes(), RevealHighlight(), RevealMath.KaTeX()],
    math: {
      katexVersion: 'latest',
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$', right: '$', display: false },
      ],
    },
  });

  await revealInstance.initialize();
  revealInstance.on('slidechanged', (event) => {
    syncingFromReveal = true;
    emit('update:currentIndex', event.indexh);
    syncingFromReveal = false;
  });
  revealInstance.slide(props.currentIndex);
}

watch(
  () => props.currentIndex,
  (index) => {
    if (!revealInstance || syncingFromReveal) {
      return;
    }
    revealInstance.slide(index);
  },
);

watch(
  () => props.pages,
  async () => {
    if (!revealInstance) {
      return;
    }
    await nextTick();
    revealInstance.sync();
    revealInstance.layout();
  },
  { deep: true },
);

onMounted(() => {
  void initReveal();
});

onUnmounted(() => {
  if (revealInstance) {
    revealInstance.destroy();
    revealInstance = null;
  }
});
</script>

<template>
  <div ref="rootEl" class="reveal-stage">
    <div class="reveal">
      <div class="slides">
        <section v-for="page in pages" :key="page.slide_key" class="reveal-page" :class="[layoutClass(page), toneClass(page)]">
          <h2 class="reveal-title" v-html="richText(blockByType(page, 'title'))" />

          <ul v-if="(blockByType(page, 'key_points')?.items ?? []).length" class="reveal-key-points">
            <li
              v-for="(item, idx) in (blockByType(page, 'key_points')?.items ?? [])"
              :key="`${page.slide_key}-kp-${idx}`"
              :class="keyPointClass(page)"
            >
              {{ item }}
            </li>
          </ul>

          <section v-if="blockByType(page, 'comparison')" class="reveal-comparison">
            <table>
              <thead>
                <tr>
                  <th v-for="(column, idx) in comparisonColumns(blockByType(page, 'comparison'))" :key="`${page.slide_key}-col-${idx}`">
                    {{ column }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIdx) in comparisonRows(blockByType(page, 'comparison'))" :key="`${page.slide_key}-row-${rowIdx}`">
                  <td v-for="(cell, cellIdx) in row" :key="`${page.slide_key}-cell-${rowIdx}-${cellIdx}`">
                    {{ cell }}
                  </td>
                </tr>
              </tbody>
            </table>
          </section>

          <ol v-if="blockByType(page, 'flow')" class="reveal-flow">
            <li v-for="(step, idx) in flowSteps(blockByType(page, 'flow'))" :key="`${page.slide_key}-flow-${idx}`" class="fragment fade-right">
              {{ step }}
            </li>
          </ol>

          <section v-if="blockByType(page, 'evidence')" class="reveal-evidence" v-html="richText(blockByType(page, 'evidence'))" />

          <section v-if="blockByType(page, 'diagram_svg')?.svg_content" class="reveal-diagram">
            <SafeSvgRenderer :svg-content="blockByType(page, 'diagram_svg')?.svg_content || ''" />
          </section>

          <aside class="notes" v-if="currentPage && page.slide_key === currentPage.slide_key" v-html="richText(blockByType(page, 'speaker_note'))" />
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reveal-stage {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  aspect-ratio: 16 / 9;
  background: linear-gradient(145deg, #f4eee3, #fff8ed);
  border: 1px solid #dbc5a3;
  border-radius: 14px;
  overflow: hidden;
}

.reveal-page {
  border-radius: 14px;
  padding: 0.2em 0.3em;
  position: relative;
  overflow: hidden;
}

.reveal-page::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.35;
  mix-blend-mode: multiply;
}

.reveal-page.tone-technical {
  background: linear-gradient(155deg, #f6f8f9 0%, #edf2f5 45%, #e6edf0 100%);
  color: #17333e;
}

.reveal-page.tone-technical::before {
  background-image:
    radial-gradient(circle at 14% 12%, rgba(39, 112, 138, 0.2) 0, transparent 42%),
    linear-gradient(120deg, transparent 0, rgba(73, 127, 146, 0.16) 48%, transparent 100%);
}

.reveal-page.tone-editorial {
  background: linear-gradient(150deg, #f6f0e6 0%, #f9f6ef 52%, #f2e7d8 100%);
  color: #4a2813;
}

.reveal-page.tone-editorial::before {
  background-image:
    radial-gradient(circle at 85% 14%, rgba(190, 118, 78, 0.18) 0, transparent 45%),
    linear-gradient(135deg, transparent 0, rgba(142, 85, 54, 0.12) 46%, transparent 100%);
}

.reveal-page.tone-spotlight {
  background: radial-gradient(circle at 18% 8%, #fff8dc 0%, #efe6c8 42%, #e4d9b8 100%);
  color: #463307;
}

.reveal-page.tone-spotlight::before {
  background-image:
    radial-gradient(circle at 24% 18%, rgba(241, 181, 40, 0.28) 0, transparent 48%),
    linear-gradient(140deg, transparent 0, rgba(153, 119, 24, 0.12) 55%, transparent 100%);
}

.reveal-page.tone-warm {
  background: linear-gradient(135deg, #fff2e8 0%, #fde7d5 48%, #fbdcc4 100%);
  color: #5c2312;
}

.reveal-page.tone-warm::before {
  background-image:
    radial-gradient(circle at 79% 15%, rgba(247, 123, 76, 0.22) 0, transparent 48%),
    linear-gradient(124deg, transparent 0, rgba(188, 91, 54, 0.12) 52%, transparent 100%);
}

.reveal :deep(.slides section) {
  text-align: left;
}

.reveal-title {
  margin-bottom: 0.4em;
  position: relative;
  z-index: 1;
}

.reveal-page.layout-split-evidence {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  column-gap: 1.1em;
  align-content: start;
}

.reveal-page.layout-split-evidence .reveal-title {
  grid-column: 1 / span 2;
}

.reveal-page.layout-data-table .reveal-comparison {
  font-size: 1.05em;
}

.reveal-page.layout-process-steps .reveal-flow li {
  background: #fff7e8;
  border: 1px solid #dec9a7;
  border-radius: 10px;
  padding: 0.25em 0.45em;
}

.reveal-key-points {
  margin-bottom: 0.8em;
  position: relative;
  z-index: 1;
}

.reveal-comparison table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.72em;
}

.reveal-comparison th,
.reveal-comparison td {
  border: 1px solid #d6c4a4;
  padding: 0.4em;
}

.reveal-comparison th {
  background: #eadbc4;
}

.reveal-flow {
  margin: 0.4em 0 0.8em;
}

.reveal-evidence {
  font-size: 0.74em;
  color: #4f3615;
  position: relative;
  z-index: 1;
}

.reveal-diagram {
  margin-top: 0.6em;
  border: 1px solid #dac6a7;
  border-radius: 10px;
  background: #fffdf8;
  padding: 0.4em;
}

.reveal-diagram :deep(svg) {
  width: 100%;
  height: auto;
}
</style>
