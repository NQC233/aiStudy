<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { RouterLink, useRoute, useRouter } from 'vue-router';

import {
  ensureAssetSlideTts,
  fetchAssetDetail,
  fetchAssetSlides,
  retryNextAssetSlideTts,
  type AssetDetail,
  type AssetSlidesResponse,
  type RuntimeRenderedPage,
} from '@/api/assets';
import SlidesDeckRuntime from '@/components/slides/SlidesDeckRuntime.vue';
import { useSlidesPlaybackTimeline } from '@/composables/useSlidesPlaybackTimeline';

const route = useRoute();
const router = useRouter();
const assetId = computed(() => String(route.params.assetId ?? ''));

const loading = ref(false);
const errorMessage = ref('');
const playbackMessage = ref('');
const playbackBusy = ref(false);
const failedNextPageIndex = ref<number | null>(null);
const waitingNextPageIndex = ref<number | null>(null);
const waitingResumePlayback = ref(false);
const waitingPollTimer = ref<number | null>(null);
const rebuildingPollTimer = ref<number | null>(null);
const asset = ref<AssetDetail | null>(null);
const slidesResponse = ref<AssetSlidesResponse | null>(null);
const currentSlideIndex = ref(0);
const audioEl = ref<HTMLAudioElement | null>(null);

const pages = computed<RuntimeRenderedPage[]>(() => slidesResponse.value?.runtime_bundle?.pages ?? []);
const currentPage = computed<RuntimeRenderedPage | null>(() => pages.value[currentSlideIndex.value] ?? null);
const qualityScore = computed(() => slidesResponse.value?.quality_report?.overall_score ?? null);
const generationMeta = computed(() => slidesResponse.value?.generation_meta ?? null);
const shadowReport = computed(() => slidesResponse.value?.shadow_report ?? null);
const playbackPlan = computed(() => slidesResponse.value?.playback_plan ?? null);
const ttsManifestItems = computed(() => slidesResponse.value?.tts_manifest?.pages ?? []);
const effectiveSlidesStatus = computed(() => slidesResponse.value?.slides_status ?? asset.value?.enhanced_resources.slides_status ?? 'unknown');
const isSlidesReady = computed(() => effectiveSlidesStatus.value === 'ready');
const canGoPrev = computed(() => currentSlideIndex.value > 0);
const canGoNext = computed(() => currentSlideIndex.value < pages.value.length - 1);

const {
  isPlaying,
  autoPageEnabled,
  totalDurationMs,
  displayedGlobalMs,
  currentPageElapsedMs,
  activeCue,
  setPlaying,
  setAutoPageEnabled,
  syncToSlideStart,
  setCurrentPageElapsedMs,
  beginPreview,
  endPreviewAndGetSeekTarget,
  seekGlobalMs,
} = useSlidesPlaybackTimeline({
  pages,
  currentSlideIndex,
  playbackPlan,
});

const currentManifestItem = computed(() => {
  const pageKey = currentPage.value?.page_id;
  if (!pageKey) {
    return null;
  }
  return ttsManifestItems.value.find((item) => item.slide_key === pageKey) ?? null;
});

function formatRetryEta(eta: string | undefined): string {
  if (!eta) {
    return '';
  }
  const date = new Date(eta);
  if (Number.isNaN(date.getTime())) {
    return eta;
  }
  return date.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

const currentTtsRetryHint = computed(() => {
  const retryMeta = currentManifestItem.value?.retry_meta;
  if (!retryMeta?.auto_retry_pending) {
    return '';
  }
  const attempt = retryMeta.attempt ?? 0;
  const maxRetries = retryMeta.max_retries ?? 0;
  const eta = formatRetryEta(retryMeta.next_retry_eta);
  if (eta) {
    return `自动重试中（${attempt}/${maxRetries}），预计 ${eta}`;
  }
  return `自动重试中（${attempt}/${maxRetries}）`;
});

function currentPageTitle(page: RuntimeRenderedPage | null): string {
  if (!page) {
    return '';
  }
  return page.page_id;
}

function handleRuntimeSlideChange(index: number) {
  if (index === currentSlideIndex.value) {
    return;
  }
  void navigateToSlide(index, true);
}

function formatMs(value: number): string {
  const safe = Math.max(0, Math.floor(value / 1000));
  const minutes = String(Math.floor(safe / 60)).padStart(2, '0');
  const seconds = String(safe % 60).padStart(2, '0');
  return `${minutes}:${seconds}`;
}

const displayedDurationLabel = computed(() => `${formatMs(displayedGlobalMs.value)} / ${formatMs(totalDurationMs.value)}`);

function clampCurrentSlide() {
  if (!pages.value.length) {
    currentSlideIndex.value = 0;
    return;
  }
  currentSlideIndex.value = Math.max(0, Math.min(currentSlideIndex.value, pages.value.length - 1));
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'ArrowLeft') {
    void navigateToSlide(currentSlideIndex.value - 1, true);
  }
  if (event.key === 'ArrowRight') {
    void navigateToSlide(currentSlideIndex.value + 1, true);
  }
}

async function refreshSlides() {
  const [assetDetail, slides] = await Promise.all([
    fetchAssetDetail(assetId.value),
    fetchAssetSlides(assetId.value),
  ]);
  asset.value = assetDetail;
  slidesResponse.value = slides;
}

async function loadSlides() {
  loading.value = true;
  errorMessage.value = '';

  try {
    await refreshSlides();
    const slides = slidesResponse.value;

    if (!slides?.runtime_bundle || slides.slides_status !== 'ready') {
      if (slides?.rebuilding || slides?.rebuild_reason === 'schema_upgrade_rebuild' || slides?.slides_status === 'processing') {
        playbackMessage.value = '检测到旧版演示结构，系统正在自动升级重建，请稍后自动刷新。';
        scheduleRebuildingPoll();
        return;
      }
      throw new Error('当前演示内容尚未就绪，请先在工作区触发生成。');
    }
    clearRebuildingPoll();
    syncToSlideStart(currentSlideIndex.value);
    clampCurrentSlide();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '演示页面加载失败。';
  } finally {
    loading.value = false;
  }
}

async function ensureTtsForPage(pageIndex: number, prefetchNext = true) {
  const response = await ensureAssetSlideTts(assetId.value, {
    page_index: pageIndex,
    prefetch_next: prefetchNext,
  });
  if (response.message) {
    playbackMessage.value = response.message;
  }
}

async function loadAudioAndSeek(audioUrl: string, seekMs: number): Promise<void> {
  const audio = audioEl.value;
  if (!audio) {
    return;
  }

  const targetSec = Math.max(0, seekMs / 1000);
  if (audio.src !== audioUrl) {
    await new Promise<void>((resolve, reject) => {
      const handleLoaded = () => {
        audio.removeEventListener('loadedmetadata', handleLoaded);
        audio.removeEventListener('error', handleError);
        resolve();
      };
      const handleError = () => {
        audio.removeEventListener('loadedmetadata', handleLoaded);
        audio.removeEventListener('error', handleError);
        reject(new Error('音频加载失败。'));
      };
      audio.addEventListener('loadedmetadata', handleLoaded);
      audio.addEventListener('error', handleError);
      audio.src = audioUrl;
      audio.load();
    });
  }

  audio.currentTime = targetSec;
}

function pausePlayback(clearMessage = false) {
  const audio = audioEl.value;
  if (audio) {
    audio.pause();
  }
  setPlaying(false);
  if (clearMessage) {
    playbackMessage.value = '';
  }
}

function clearWaitingTimer() {
  if (waitingPollTimer.value !== null) {
    window.clearTimeout(waitingPollTimer.value);
    waitingPollTimer.value = null;
  }
}

function clearRebuildingPoll() {
  if (rebuildingPollTimer.value !== null) {
    window.clearTimeout(rebuildingPollTimer.value);
    rebuildingPollTimer.value = null;
  }
}

function scheduleRebuildingPoll() {
  clearRebuildingPoll();
  rebuildingPollTimer.value = window.setTimeout(() => {
    rebuildingPollTimer.value = null;
    void loadSlides();
  }, 2500);
}

function clearWaitingState() {
  waitingNextPageIndex.value = null;
  waitingResumePlayback.value = false;
  clearWaitingTimer();
}

function scheduleWaitingNextPagePoll() {
  clearWaitingTimer();
  waitingPollTimer.value = window.setTimeout(() => {
    waitingPollTimer.value = null;
    void pollWaitingNextPage();
  }, 2500);
}

async function pollWaitingNextPage() {
  const nextIndex = waitingNextPageIndex.value;
  if (nextIndex === null) {
    return;
  }

  try {
    await ensureTtsForPage(nextIndex, true);
    await refreshSlides();
    const nextPage = pages.value[nextIndex];
    const nextManifest = ttsManifestItems.value.find((item) => item.slide_key === nextPage?.page_id);
    if (!nextManifest) {
      clearWaitingState();
      playbackMessage.value = '下一页状态异常，请手动重试。';
      return;
    }

    if (nextManifest.status === 'ready' && nextManifest.audio_url) {
      const shouldResume = waitingResumePlayback.value;
      clearWaitingState();
      currentSlideIndex.value = nextIndex;
      syncToSlideStart(nextIndex);
      if (shouldResume) {
        await startPlaybackForCurrentSlide(0);
      }
      return;
    }

    if (nextManifest.status === 'failed') {
      clearWaitingState();
      failedNextPageIndex.value = nextIndex;
      playbackMessage.value = `下一页音频生成失败：${nextManifest.error_message || '未知错误'}。请点击“重试下一页”。`;
      return;
    }

    scheduleWaitingNextPagePoll();
  } catch (error) {
    clearWaitingState();
    playbackMessage.value = error instanceof Error ? error.message : '轮询下一页状态失败。';
  }
}

async function startPlaybackForCurrentSlide(seekMs: number) {
  if (!currentPage.value) {
    return;
  }
  playbackBusy.value = true;
  failedNextPageIndex.value = null;
  try {
    await ensureTtsForPage(currentSlideIndex.value, true);
    await refreshSlides();
    const manifestItem = currentManifestItem.value;
    if (!manifestItem || manifestItem.status !== 'ready' || !manifestItem.audio_url) {
      pausePlayback();
      playbackMessage.value = manifestItem?.status === 'failed'
        ? (manifestItem.error_message || '当前页音频生成失败，请重试。')
        : '当前页音频生成中，请稍后点击播放继续。';
      return;
    }

    await loadAudioAndSeek(manifestItem.audio_url, seekMs);
    const audio = audioEl.value;
    if (!audio) {
      return;
    }
    await audio.play();
    setPlaying(true);
  } catch (error) {
    pausePlayback();
    playbackMessage.value = error instanceof Error ? error.message : '播放失败，请稍后重试。';
  } finally {
    playbackBusy.value = false;
  }
}

async function handleAutoAdvanceAfterEnded() {
  if (!autoPageEnabled.value || !canGoNext.value) {
    setPlaying(false);
    return;
  }

  const nextIndex = currentSlideIndex.value + 1;
  try {
    await ensureTtsForPage(nextIndex, true);
    await refreshSlides();
    const nextPage = pages.value[nextIndex];
    const nextManifest = ttsManifestItems.value.find((item) => item.slide_key === nextPage?.page_id);
    if (nextManifest?.status === 'failed') {
      clearWaitingState();
      failedNextPageIndex.value = nextIndex;
      pausePlayback();
      playbackMessage.value = `下一页音频生成失败：${nextManifest.error_message || '未知错误'}。请点击“重试下一页”。`;
      return;
    }
    if (nextManifest?.status !== 'ready') {
      pausePlayback();
      failedNextPageIndex.value = null;
      waitingNextPageIndex.value = nextIndex;
      waitingResumePlayback.value = true;
      playbackMessage.value = '下一页音频生成中，已自动暂停并等待就绪后续播。';
      scheduleWaitingNextPagePoll();
      return;
    }

    clearWaitingState();
    currentSlideIndex.value = nextIndex;
    syncToSlideStart(nextIndex);
    await startPlaybackForCurrentSlide(0);
  } catch (error) {
    pausePlayback();
    playbackMessage.value = error instanceof Error ? error.message : '自动翻页失败。';
  }
}

async function navigateToSlide(index: number, fromUser: boolean) {
  if (index < 0 || index >= pages.value.length) {
    return;
  }
  const shouldResume = fromUser && isPlaying.value;
  clearWaitingState();
  pausePlayback();
  currentSlideIndex.value = index;
  syncToSlideStart(index);
  if (shouldResume) {
    await startPlaybackForCurrentSlide(0);
  }
}

async function togglePlayPause() {
  if (isPlaying.value) {
    pausePlayback(true);
    return;
  }
  await startPlaybackForCurrentSlide(currentPageElapsedMs.value);
}

function onTimelineInput(event: Event) {
  const value = Number((event.target as HTMLInputElement).value || 0);
  beginPreview(value);
}

async function onTimelineCommit() {
  const target = endPreviewAndGetSeekTarget();
  const seekTarget = seekGlobalMs(target);
  const shouldResume = isPlaying.value;
  clearWaitingState();
  pausePlayback();
  currentSlideIndex.value = seekTarget.pageIndex;
  setCurrentPageElapsedMs(seekTarget.pageElapsedMs);
  if (shouldResume) {
    await startPlaybackForCurrentSlide(seekTarget.pageElapsedMs);
  }
}

async function retryNextPage() {
  if (failedNextPageIndex.value === null) {
    return;
  }
  playbackBusy.value = true;
  try {
    clearWaitingState();
    const response = await retryNextAssetSlideTts(assetId.value, {
      current_page_index: currentSlideIndex.value,
    });
    playbackMessage.value = response.message;
    await refreshSlides();
    if (failedNextPageIndex.value !== null) {
      waitingNextPageIndex.value = failedNextPageIndex.value;
      waitingResumePlayback.value = true;
      failedNextPageIndex.value = null;
      scheduleWaitingNextPagePoll();
    }
  } catch (error) {
    playbackMessage.value = error instanceof Error ? error.message : '重试下一页失败。';
  } finally {
    playbackBusy.value = false;
  }
}

function jumpToCitation(pageNo: number, blockId: string | null) {
  void router.push({
    name: 'workspace',
    params: { assetId: assetId.value },
    query: {
      page: String(pageNo),
      blockId: blockId ?? '',
      source: 'slides',
    },
  });
}

async function backToWorkspace() {
  await router.push({
    name: 'workspace',
    params: { assetId: assetId.value },
  });
}

async function recoverSlidesAndBack() {
  await router.push({
    name: 'workspace',
    params: { assetId: assetId.value },
    query: { source: 'slides-runtime-migration' },
  });
}

watch(
  () => route.params.assetId,
  () => {
    currentSlideIndex.value = 0;
    void loadSlides();
  },
);

watch(
  () => slidesResponse.value?.slides_status,
  (status) => {
    if (status === 'processing' && slidesResponse.value?.rebuilding) {
      scheduleRebuildingPoll();
    } else if (status === 'ready') {
      clearRebuildingPoll();
    }
  },
);

watch(
  () => pages.value.length,
  () => {
    clampCurrentSlide();
  },
);

onMounted(() => {
  const audio = new Audio();
  audioEl.value = audio;
  audio.addEventListener('timeupdate', () => {
    setCurrentPageElapsedMs(audio.currentTime * 1000);
  });
  audio.addEventListener('ended', () => {
    void handleAutoAdvanceAfterEnded();
  });
  audio.addEventListener('error', () => {
    pausePlayback();
    playbackMessage.value = '音频播放异常，请重试。';
  });
  window.addEventListener('keydown', handleKeydown);
  void loadSlides();
});

onUnmounted(() => {
  clearRebuildingPoll();
  clearWaitingState();
  pausePlayback();
  if (audioEl.value) {
    audioEl.value.src = '';
    audioEl.value = null;
  }
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<template>
  <main class="slides-page">
    <section class="slides-shell">
      <header class="slides-header">
        <div>
          <p class="slides-kicker">Slides / Spec 12</p>
          <h1>{{ asset?.title ?? '演示播放页' }}</h1>
          <p class="slides-meta">
            状态：{{ effectiveSlidesStatus }}
            <span v-if="qualityScore !== null"> · 质量分：{{ qualityScore.toFixed(2) }}</span>
          </p>
          <p class="slides-meta">
            TTS：{{ slidesResponse?.tts_status ?? 'not_generated' }}
            <span> · Playback：{{ slidesResponse?.playback_status ?? 'not_ready' }}</span>
          </p>
          <p v-if="generationMeta && isSlidesReady" class="slides-meta">
            策略：{{ generationMeta.requested_strategy }} → {{ generationMeta.applied_strategy }}
            <span v-if="generationMeta.fallback_used"> · 已回退（{{ generationMeta.fallback_reason || 'unknown' }}）</span>
          </p>
          <p v-else-if="!isSlidesReady" class="slides-meta">策略结果更新中，请等待当前生成完成。</p>
          <p v-if="shadowReport && isSlidesReady" class="slides-meta">
            Shadow：{{ shadowReport.status }}
            <span v-if="shadowReport.score_delta !== null"> · Δ{{ shadowReport.score_delta.toFixed(2) }}</span>
            <span v-else-if="shadowReport.skip_reason"> · {{ shadowReport.skip_reason }}</span>
          </p>
        </div>
        <RouterLink :to="`/workspace/${assetId}`" class="slides-back">
          返回工作区
        </RouterLink>
      </header>

      <section v-if="loading" class="slides-empty">
        正在加载演示内容...
      </section>
      <section v-else-if="errorMessage" class="slides-empty slides-empty--error">
        <p class="slides-error-message">{{ errorMessage }}</p>
        <div class="slides-error-actions">
          <button type="button" class="toolbar-button toolbar-button--ghost" @click="backToWorkspace">
            返回工作区
          </button>
          <button type="button" class="toolbar-button" @click="recoverSlidesAndBack">
            返回工作区
          </button>
        </div>
      </section>

      <section v-else class="slides-layout">
        <section class="slides-stage">
          <header class="slides-stage__toolbar">
            <button type="button" class="toolbar-button toolbar-button--ghost" :disabled="!canGoPrev" @click="navigateToSlide(currentSlideIndex - 1, true)">
              上一页
            </button>
            <p class="slides-stage__counter">
              {{ pages.length ? `${currentSlideIndex + 1} / ${pages.length}` : '0 / 0' }}
            </p>
            <button type="button" class="toolbar-button" :disabled="!canGoNext" @click="navigateToSlide(currentSlideIndex + 1, true)">
              下一页
            </button>
          </header>
          <p class="slides-stage__hint">快捷键：← / → 切换页面</p>

          <section class="slides-player-bar">
            <button type="button" class="toolbar-button" :disabled="playbackBusy" @click="togglePlayPause">
              {{ isPlaying ? '暂停' : '播放' }}
            </button>
            <label class="slides-player-bar__auto">
              <input
                type="checkbox"
                :checked="autoPageEnabled"
                @change="setAutoPageEnabled(($event.target as HTMLInputElement).checked)"
              />
              自动翻页
            </label>
            <input
              class="slides-player-bar__range"
              type="range"
              min="0"
              :max="Math.max(totalDurationMs, 1)"
              :value="displayedGlobalMs"
              @input="onTimelineInput"
              @change="onTimelineCommit"
            />
            <span class="slides-player-bar__time">{{ displayedDurationLabel }}</span>
          </section>

          <p v-if="playbackMessage" class="slides-playback-message">{{ playbackMessage }}</p>
          <button
            v-if="failedNextPageIndex !== null"
            type="button"
            class="toolbar-button"
            :disabled="playbackBusy"
            @click="retryNextPage"
          >
            重试下一页
          </button>

          <nav v-if="pages.length" class="slides-page-nav" aria-label="演示分页目录">
            <button
              v-for="(page, index) in pages"
              :key="page.page_id"
              type="button"
              class="slides-page-nav__item"
              :class="{ 'slides-page-nav__item--active': index === currentSlideIndex }"
              @click="navigateToSlide(index, true)"
            >
              <span class="slides-page-nav__index">{{ index + 1 }}</span>
              <span class="slides-page-nav__title">{{ currentPageTitle(page) }}</span>
            </button>
          </nav>

          <SlidesDeckRuntime
            v-if="pages.length"
            :pages="pages"
            :current-index="currentSlideIndex"
            @update:current-index="handleRuntimeSlideChange"
          />
          <section v-else class="slides-empty">暂无可播放页面。</section>
        </section>

        <aside class="slides-notes">
          <header>
            <p class="slides-kicker">Speaker Notes</p>
            <h2>{{ currentPage?.page_id ?? '未选中页面' }}</h2>
          </header>

          <p class="slides-script">
            {{ currentPage ? '当前 runtime 页面已就绪；讲稿与引用锚点待后续 runtime payload 接入。' : '切换页面后查看讲稿。' }}
          </p>
          <p class="slides-meta">
            当前页音频：{{ currentManifestItem?.status ?? 'pending' }}
          </p>
          <p v-if="currentTtsRetryHint" class="slides-meta slides-meta--retry">{{ currentTtsRetryHint }}</p>

          <p class="slides-citation-empty">当前 runtime 页面暂无引用锚点展示。</p>
        </aside>
      </section>
    </section>
  </main>
</template>

<style scoped>
.slides-page {
  min-height: 100vh;
  padding: 1.25rem;
  background: radial-gradient(circle at 0% 0%, #f6f0df 0%, #f2efe8 30%, #ebe9e1 100%);
  font-family: 'Avenir Next', 'Segoe UI', sans-serif;
  color: #1f2730;
}

.slides-shell {
  max-width: 1380px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.slides-header {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  align-items: flex-start;
}

.slides-kicker {
  margin: 0;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.14em;
  color: #965d17;
}

.slides-header h1 {
  margin: 0.35rem 0;
  font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
  font-size: 2rem;
}

.slides-meta {
  margin: 0;
  color: #4d5b6b;
}

.slides-meta--retry {
  color: #7b3f00;
}

.slides-back {
  text-decoration: none;
  color: #fff;
  background: linear-gradient(135deg, #9a5f17, #6d4010);
  padding: 0.65rem 0.95rem;
  border-radius: 0.75rem;
}

.slides-empty {
  background: #fff;
  border-radius: 1rem;
  padding: 1.25rem;
}

.slides-empty--error {
  background: #fbe9e9;
  color: #8a1f1f;
}

.slides-error-message {
  margin: 0;
}

.slides-error-actions {
  margin-top: 0.85rem;
  display: flex;
  gap: 0.65rem;
  flex-wrap: wrap;
}

.slides-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 1rem;
}

.slides-stage,
.slides-notes {
  background: #fff;
  border-radius: 1rem;
  border: 1px solid #d9d7cf;
  padding: 1rem;
}

.slides-stage__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.85rem;
}

.slides-stage__counter {
  margin: 0;
  color: #556274;
  font-weight: 600;
}

.slides-stage__hint {
  margin: 0 0 0.7rem;
  color: #687586;
  font-size: 0.88rem;
}

.slides-player-bar {
  display: grid;
  grid-template-columns: auto auto minmax(0, 1fr) auto;
  gap: 0.65rem;
  align-items: center;
  margin-bottom: 0.75rem;
}

.slides-player-bar__auto {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  color: #5c6878;
  font-size: 0.88rem;
}

.slides-player-bar__range {
  width: 100%;
}

.slides-player-bar__time {
  color: #5c6878;
  font-variant-numeric: tabular-nums;
  font-size: 0.82rem;
}

.slides-playback-message {
  margin: 0 0 0.75rem;
  color: #7b3f00;
  background: #fff3e2;
  border: 1px solid #e5c99f;
  border-radius: 0.7rem;
  padding: 0.5rem 0.7rem;
}

.slides-page-nav {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.5rem;
  margin-bottom: 0.85rem;
}

.slides-page-nav__item {
  border: 1px solid #dccfb6;
  border-radius: 0.7rem;
  background: #fff9ef;
  color: #61401c;
  padding: 0.5rem 0.6rem;
  display: flex;
  align-items: center;
  gap: 0.45rem;
  text-align: left;
  cursor: pointer;
}

.slides-page-nav__item:hover {
  border-color: #ba8a4d;
  background: #fff4df;
}

.slides-page-nav__item--active {
  border-color: #8e5a22;
  background: #f6e7cf;
}

.slides-page-nav__index {
  width: 1.45rem;
  height: 1.45rem;
  border-radius: 50%;
  background: #e9d5b4;
  color: #6e4417;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  flex-shrink: 0;
}

.slides-page-nav__title {
  font-size: 0.88rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toolbar-button {
  border: 1px solid #ab7c44;
  border-radius: 0.7rem;
  background: linear-gradient(135deg, #9a5f17, #6d4010);
  color: #fff;
  padding: 0.42rem 0.85rem;
  cursor: pointer;
}

.toolbar-button--ghost {
  background: #fff9ef;
  color: #7a4d1f;
}

.toolbar-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.slides-section h2 {
  margin-top: 0;
  font-family: 'Iowan Old Style', 'Palatino Linotype', serif;
  color: #7a4310;
}

.slides-goal {
  font-weight: 600;
}

.slides-key-points {
  margin: 0 0 0.7rem;
  padding-left: 1.2rem;
  display: grid;
  gap: 0.3rem;
  color: #2f3a4a;
}

.slides-section__active-cue {
  background: #fff4df;
  border-left: 3px solid #b26f24;
  padding-left: 0.55rem;
}

.slides-evidence {
  opacity: 0.86;
}

.slides-script {
  margin: 0.75rem 0;
  line-height: 1.5;
}

.slides-citations {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.slides-citation-button {
  width: 100%;
  border: 1px solid #d8d1c3;
  border-radius: 0.8rem;
  padding: 0.65rem;
  background: #fff8ec;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  cursor: pointer;
}

.slides-citation-button:hover {
  border-color: #b1762f;
  background: #fff1dc;
}

.slides-citation-empty {
  color: #6a7483;
}

@media (max-width: 980px) {
  .slides-layout {
    grid-template-columns: 1fr;
  }

  .slides-header {
    flex-direction: column;
  }

  .slides-player-bar {
    grid-template-columns: 1fr;
  }
}
</style>
