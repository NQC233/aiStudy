<script setup lang="ts">
import SafeSvgRenderer from '@/components/slides/SafeSvgRenderer.vue';
import type { SlideDslBlock } from '@/api/assets';

defineProps<{
  block: SlideDslBlock;
  active: boolean;
}>();

function comparisonColumns(block: SlideDslBlock): string[] {
  const value = block.meta?.columns;
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
    return value;
  }
  return ['方案', '说明', '结论'];
}

function comparisonRows(block: SlideDslBlock): string[][] {
  const value = block.meta?.rows;
  if (Array.isArray(value)) {
    const rows = value
      .filter((row): row is unknown[] => Array.isArray(row))
      .map((row) => row.map((cell) => String(cell)));
    if (rows.length) {
      return rows;
    }
  }
  return (block.items || []).map((row) => row.split('｜').map((cell) => cell.trim()));
}

function flowSteps(block: SlideDslBlock): string[] {
  const value = block.meta?.steps;
  if (Array.isArray(value) && value.every((item) => typeof item === 'string')) {
    return value;
  }
  return block.items || [];
}
</script>

<template>
  <p v-if="block.block_type === 'speaker_note'" class="slides-block slides-block--speaker" :class="{ 'slides-section__active-cue': active }">
    {{ block.content }}
  </p>

  <ul v-else-if="block.block_type === 'key_points'" class="slides-block slides-key-points" :class="{ 'slides-section__active-cue': active }">
    <li v-for="(item, idx) in (block.items || [])" :key="`kp-${idx}`">{{ item }}</li>
  </ul>

  <p v-else-if="block.block_type === 'evidence'" class="slides-block slides-evidence" :class="{ 'slides-section__active-cue': active }">
    {{ (block.items || []).length ? (block.items || []).join('；') : block.content }}
  </p>

  <section v-else-if="block.block_type === 'diagram_svg'" class="slides-block slides-diagram" :class="{ 'slides-section__active-cue': active }">
    <SafeSvgRenderer :svg-content="block.svg_content || ''" />
  </section>

  <section v-else-if="block.block_type === 'comparison'" class="slides-block slides-comparison" :class="{ 'slides-section__active-cue': active }">
    <div class="slides-comparison__row slides-comparison__row--header">
      <span v-for="(column, idx) in comparisonColumns(block)" :key="`cmp-head-${idx}`" class="slides-comparison__cell slides-comparison__cell--header">
        {{ column }}
      </span>
    </div>
    <div v-for="(row, idx) in comparisonRows(block)" :key="`cmp-${idx}`" class="slides-comparison__row">
      <span v-for="(cell, cellIdx) in row" :key="`cmp-${idx}-${cellIdx}`" class="slides-comparison__cell">
        {{ cell }}
      </span>
    </div>
  </section>

  <ol v-else-if="block.block_type === 'flow'" class="slides-block slides-flow" :class="{ 'slides-section__active-cue': active }">
    <li v-for="(step, idx) in flowSteps(block)" :key="`flow-${idx}`" class="slides-flow__step">
      <span class="slides-flow__index">{{ idx + 1 }}</span>
      <span>{{ step }}</span>
    </li>
  </ol>

  <p v-else-if="block.block_type === 'takeaway'" class="slides-block slides-takeaway" :class="{ 'slides-section__active-cue': active }">
    {{ block.content }}
  </p>

  <p v-else-if="block.block_type !== 'title'" class="slides-block" :class="{ 'slides-section__active-cue': active }">
    {{ block.content || ((block.items || []).length ? (block.items || []).join('；') : '') }}
  </p>
</template>

<style scoped>
.slides-block {
  margin: 0 0 0.7rem;
}

.slides-diagram {
  border: 1px solid #dfceb0;
  border-radius: 0.8rem;
  padding: 0.55rem;
  background: #fffbf4;
}

.slides-takeaway {
  padding: 0.55rem 0.65rem;
  border-radius: 0.7rem;
  background: #fdf3e5;
  border-left: 3px solid #b26f24;
}

.slides-comparison {
  display: grid;
  gap: 0.45rem;
}

.slides-comparison__row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0.4rem;
}

.slides-comparison__row--header .slides-comparison__cell {
  background: #f4e8d5;
  color: #643f15;
  font-weight: 700;
}

.slides-comparison__cell {
  padding: 0.38rem 0.45rem;
  border-radius: 0.55rem;
  border: 1px solid #dfceb0;
  background: #fffbf4;
  font-size: 0.92rem;
}

.slides-comparison__cell--header {
  text-align: center;
}

.slides-flow {
  margin: 0 0 0.7rem;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 0.4rem;
}

.slides-flow__step {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.42rem 0.5rem;
  border-radius: 0.6rem;
  background: #fff7ea;
  border: 1px solid #e6d5b8;
}

.slides-flow__index {
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #704315;
  background: #efd8b7;
  flex-shrink: 0;
}
</style>
