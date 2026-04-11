<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  svgContent: string;
}>();

const ALLOWED_TAGS = new Set([
  'svg',
  'g',
  'path',
  'rect',
  'circle',
  'ellipse',
  'line',
  'polyline',
  'polygon',
  'text',
  'tspan',
  'defs',
  'clipPath',
  'linearGradient',
  'radialGradient',
  'stop',
]);

const ALLOWED_ATTRS = new Set([
  'xmlns',
  'viewBox',
  'x',
  'y',
  'x1',
  'x2',
  'y1',
  'y2',
  'cx',
  'cy',
  'r',
  'rx',
  'ry',
  'width',
  'height',
  'd',
  'points',
  'fill',
  'stroke',
  'stroke-width',
  'stroke-linecap',
  'stroke-linejoin',
  'opacity',
  'fill-opacity',
  'stroke-opacity',
  'font-size',
  'font-family',
  'font-weight',
  'text-anchor',
  'transform',
  'id',
  'offset',
  'stop-color',
  'stop-opacity',
]);

function sanitizeSvg(raw: string): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(raw, 'image/svg+xml');
  const root = doc.documentElement;
  if (!root || root.tagName.toLowerCase() !== 'svg') {
    return '';
  }

  const walk = (node: Element) => {
    const children = Array.from(node.children);
    for (const child of children) {
      const tag = child.tagName;
      if (!ALLOWED_TAGS.has(tag)) {
        child.remove();
        continue;
      }
      for (const attr of Array.from(child.attributes)) {
        const name = attr.name;
        const value = attr.value;
        if (!ALLOWED_ATTRS.has(name) || name.startsWith('on') || value.includes('javascript:')) {
          child.removeAttribute(name);
        }
      }
      walk(child);
    }
  };

  for (const attr of Array.from(root.attributes)) {
    const name = attr.name;
    const value = attr.value;
    if (!ALLOWED_ATTRS.has(name) || name.startsWith('on') || value.includes('javascript:')) {
      root.removeAttribute(name);
    }
  }
  walk(root);
  return root.outerHTML;
}

const safeSvg = computed(() => sanitizeSvg(props.svgContent || ''));
</script>

<template>
  <div class="safe-svg" v-html="safeSvg" />
</template>

<style scoped>
.safe-svg :deep(svg) {
  max-width: 100%;
  height: auto;
  display: block;
}
</style>
