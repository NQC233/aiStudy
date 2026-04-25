<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  html: string;
  css: string;
}>();

const srcdoc = computed(() => `<!DOCTYPE html>
<html style="width:100%;height:100%;margin:0;overflow:hidden;">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <style>${props.css}</style>
    <style>
      #claude-slide-frame-root {
        position: fixed;
        inset: 0;
        overflow: hidden;
      }

      #claude-slide-frame-canvas {
        position: absolute;
        left: 50%;
        top: 50%;
        width: 1600px;
        height: 900px;
        transform-origin: center center;
        will-change: transform;
      }
    </style>
  </head>
  <body style="width:100%;height:100%;margin:0;overflow:hidden;">
    <div id="claude-slide-frame-root">
      <div id="claude-slide-frame-canvas">${props.html}</div>
    </div>
    <script>
      (function () {
        const canvas = document.getElementById('claude-slide-frame-canvas');
        if (!canvas) {
          return;
        }

        function applyScale() {
          const scale = Math.min(window.innerWidth / 1600, window.innerHeight / 900);
          canvas.style.transform = 'translate(-50%, -50%) scale(' + scale + ')';
        }

        window.addEventListener('resize', applyScale);
        applyScale();
      })();
    <\/script>
  </body>
</html>`);
</script>

<template>
  <iframe
    class="slide-frame"
    :srcdoc="srcdoc"
    title="Rendered slide page"
  />
</template>

<style scoped>
.slide-frame {
  display: block;
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 0;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
}
</style>

