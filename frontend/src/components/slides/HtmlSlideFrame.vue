<script setup lang="ts">
const props = defineProps<{
  html: string;
  css: string;
}>();
</script>

<template>
  <iframe
    class="slide-frame"
    :srcdoc="`<style>${props.css}</style>${props.html}`"
    title="Rendered slide page"
  />
</template>

<style scoped>
.slide-frame {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 0;
  border-radius: 14px;
  background: #fff;
}
</style>
