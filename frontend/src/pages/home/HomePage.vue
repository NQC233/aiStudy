<script setup lang="ts">
const stackItems = [
  'Vue 3 + TypeScript',
  'FastAPI + Celery',
  'PostgreSQL + pgvector',
  'Docker Compose',
];
</script>

<template>
  <main class="home-page">
    <section class="hero-panel">
      <p class="eyebrow">Spec 01 / Project Bootstrap</p>
      <h1>智能化论文学习平台</h1>
      <p class="hero-copy">
        当前页面用于验证前端工程骨架已经可运行。后续图书馆、工作区、阅读器与问答模块会在后续
        Spec 中逐步接入。
      </p>

      <div class="stack-grid">
        <article
          v-for="item in stackItems"
          :key="item"
          class="stack-card"
        >
          <span class="stack-index">00{{ stackItems.indexOf(item) + 1 }}</span>
          <h2>{{ item }}</h2>
        </article>
      </div>
    </section>

    <section class="status-strip">
      <div>
        <span class="status-label">当前状态</span>
        <strong>工程骨架初始化中</strong>
      </div>

      <div>
        <span class="status-label">下一步</span>
        <strong>Spec 02：学习资产模型与图书馆页</strong>
      </div>
    </section>
  </main>
</template>
