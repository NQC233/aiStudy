<script setup lang="ts">
import { computed, ref } from 'vue';

import { uploadAsset, type AssetUploadResponse } from '@/api/assets';

const emit = defineEmits<{
  close: [];
  success: [payload: AssetUploadResponse];
}>();

const title = ref('');
const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const errorMessage = ref('');

const fileLabel = computed(() => {
  return selectedFile.value?.name ?? '尚未选择 PDF 文件';
});

function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement;
  selectedFile.value = target.files?.[0] ?? null;
  errorMessage.value = '';
}

async function submitUpload() {
  if (!selectedFile.value) {
    errorMessage.value = '请先选择一个 PDF 文件。';
    return;
  }

  uploading.value = true;
  errorMessage.value = '';

  try {
    const result = await uploadAsset(selectedFile.value, title.value);
    emit('success', result);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '上传失败。';
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <div class="upload-dialog__backdrop" @click.self="emit('close')">
    <section class="upload-dialog">
      <header class="upload-dialog__header">
        <div>
          <p class="page-kicker">Upload / Spec 03</p>
          <h2>上传论文 PDF</h2>
        </div>

        <button type="button" class="upload-dialog__close" @click="emit('close')">
          关闭
        </button>
      </header>

      <label class="upload-dialog__field">
        <span>资产标题（可选）</span>
        <input
          v-model="title"
          type="text"
          placeholder="默认使用文件名作为资产标题"
        />
      </label>

      <label class="upload-dialog__field upload-dialog__field--file">
        <span>选择 PDF 文件</span>
        <input type="file" accept="application/pdf,.pdf" @change="handleFileChange" />
        <strong>{{ fileLabel }}</strong>
      </label>

      <p v-if="errorMessage" class="upload-dialog__error">
        {{ errorMessage }}
      </p>

      <footer class="upload-dialog__footer">
        <button type="button" class="upload-dialog__close" @click="emit('close')">
          取消
        </button>
        <button type="button" class="toolbar-button" :disabled="uploading" @click="submitUpload">
          {{ uploading ? '上传中...' : '开始上传' }}
        </button>
      </footer>
    </section>
  </div>
</template>
