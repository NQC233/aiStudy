<script setup lang="ts">
import { computed } from 'vue';

import type { AssetMindmapResponse, MindmapNodeItem } from '@/api/assets';

const props = defineProps<{
  mindmapData: AssetMindmapResponse | null;
  loading: boolean;
  errorMessage: string;
  rebuilding: boolean;
}>();

const emit = defineEmits<{
  'node-click': [node: MindmapNodeItem];
  rebuild: [];
}>();

const orderedNodes = computed(() => {
  const nodes = props.mindmapData?.mindmap?.nodes ?? [];
  if (!nodes.length) {
    return [] as MindmapNodeItem[];
  }

  const byParent = new Map<string | null, MindmapNodeItem[]>();
  for (const node of nodes) {
    const parentKey = node.parent_key ?? null;
    const list = byParent.get(parentKey) ?? [];
    list.push(node);
    byParent.set(parentKey, list);
  }
  for (const list of byParent.values()) {
    list.sort((a, b) => a.order - b.order);
  }

  const visited = new Set<string>();
  const ordered: MindmapNodeItem[] = [];

  function walk(parentKey: string | null) {
    const children = byParent.get(parentKey) ?? [];
    for (const node of children) {
      if (visited.has(node.node_key)) {
        continue;
      }
      visited.add(node.node_key);
      ordered.push(node);
      walk(node.node_key);
    }
  }

  walk(null);
  for (const node of [...nodes].sort((a, b) => a.level - b.level || a.order - b.order)) {
    if (visited.has(node.node_key)) {
      continue;
    }
    visited.add(node.node_key);
    ordered.push(node);
  }
  return ordered;
});

const mindmapStatusLabel = computed(() => props.mindmapData?.mindmap_status ?? 'not_started');
const mindmapVersionLabel = computed(() => props.mindmapData?.mindmap?.version ?? null);

function formatNodePage(node: MindmapNodeItem): string {
  if (node.page_no === null || node.page_no === undefined) {
    return '页码未知';
  }
  return `P${node.page_no}`;
}

function onNodeClick(node: MindmapNodeItem) {
  emit('node-click', node);
}

function onRebuildClick() {
  emit('rebuild');
}
</script>

<template>
  <header class="workspace-panel__header">
    <div>
      <p class="page-kicker">Mindmap</p>
      <h2>论文导图</h2>
    </div>
    <div class="mindmap-panel-meta">
      <span class="mindmap-status">{{ mindmapStatusLabel }}</span>
      <span v-if="mindmapVersionLabel !== null" class="mindmap-version">v{{ mindmapVersionLabel }}</span>
    </div>
  </header>

  <div class="mindmap-panel-actions">
    <button class="toolbar-button toolbar-button--ghost" type="button" :disabled="rebuilding" @click="onRebuildClick">
      {{ rebuilding ? '重建中...' : '重建导图' }}
    </button>
  </div>

  <p v-if="loading" class="workspace-muted">正在加载导图...</p>
  <p v-else-if="errorMessage" class="workspace-parse-error">{{ errorMessage }}</p>
  <p v-else-if="!orderedNodes.length" class="workspace-muted">当前资产还没有可用导图，解析完成后会自动生成。</p>

  <div v-else class="mindmap-node-list">
    <button
      v-for="node in orderedNodes"
      :key="node.id"
      class="mindmap-node"
      type="button"
      :style="{ '--mindmap-indent': String(Math.max(node.level, 0)) }"
      @click="onNodeClick(node)"
    >
      <div class="mindmap-node__title-row">
        <strong>{{ node.title }}</strong>
        <span>{{ formatNodePage(node) }}</span>
      </div>
      <p v-if="node.summary">{{ node.summary }}</p>
      <small v-if="node.node_key === 'root'">根节点</small>
    </button>
  </div>
</template>

<style scoped>
.mindmap-panel-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.mindmap-status,
.mindmap-version {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid rgba(216, 197, 154, 0.2);
  padding: 4px 10px;
  font-size: 12px;
  color: var(--text-secondary);
}

.mindmap-panel-actions {
  margin-top: 16px;
}

.mindmap-node-list {
  margin-top: 16px;
  display: grid;
  gap: 10px;
  max-height: 38vh;
  overflow: auto;
}

.mindmap-node {
  width: 100%;
  border-radius: 14px;
  border: 1px solid rgba(216, 197, 154, 0.14);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text-primary);
  padding: 10px 12px 10px calc(12px + (var(--mindmap-indent, 0) * 14px));
  text-align: left;
  cursor: pointer;
}

.mindmap-node__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mindmap-node__title-row strong {
  min-width: 0;
  overflow-wrap: anywhere;
}

.mindmap-node__title-row span {
  flex: 0 0 auto;
  color: var(--accent);
  font-size: 12px;
}

.mindmap-node p {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.mindmap-node small {
  display: inline-block;
  margin-top: 6px;
  color: var(--text-secondary);
}
</style>
